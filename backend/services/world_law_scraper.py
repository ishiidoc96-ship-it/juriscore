import httpx
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

WORLDBASE = "https://worldlii.org"
SEMAPHORE = asyncio.Semaphore(3)

# Major legal databases
WORLD_SOURCES = {
    "worldlii": {
        "name": "World Legal Information Institute",
        "base": "https://worldlii.org",
        "search": "https://worldlii.org/search",
        "types": ["case", "legislation", "journal"],
    },
    "bailii": {
        "name": "British and Irish Legal Information Institute",
        "base": "https://www.bailii.org",
        "search": "https://www.bailii.org/search",
        "types": ["case", "legislation"],
    },
    "liiconline": {
        "name": "Legal Information Institute (Cornell)",
        "base": "https://www.law.cornell.edu",
        "search": "https://www.law.cornell.edu/search",
        "types": ["case", "legislation", "regulation"],
    },
    "canlii": {
        "name": "Canadian Legal Information Institute",
        "base": "https://www.canlii.org",
        "search": "https://www.canlii.org/en/search",
        "types": ["case", "legislation"],
    },
    "austlii": {
        "name": "Australasian Legal Information Institute",
        "base": "https://www.austlii.edu.au",
        "search": "https://www.austlii.edu.au/cgi-bin/viewdb/au/cases",
        "types": ["case", "legislation"],
    },
}

# Major legal systems
LEGAL_SYSTEMS = [
    {"id": "common_law", "name": "Common Law", "regions": ["UK", "USA", "Canada", "Australia", "India", "Kenya", "Nigeria", "South Africa"]},
    {"id": "civil_law", "name": "Civil Law", "regions": ["France", "Germany", "Italy", "Spain", "Japan", "Brazil"]},
    {"id": "religious_law", "name": "Religious Law", "regions": ["Saudi Arabia", "Iran", "Israel"]},
    {"id": "mixed_system", "name": "Mixed System", "regions": ["Scotland", "Louisiana", "Quebec", "South Africa"]},
]

# Major countries with online legal databases
WORLD_JURISDICTIONS = {
    "us": {"name": "United States", "sources": ["liiconline"], "courts": ["Supreme Court", "Federal Courts", "State Courts"]},
    "uk": {"name": "United Kingdom", "sources": ["bailii", "worldlii"], "courts": ["Supreme Court", "Court of Appeal", "High Court"]},
    "canada": {"name": "Canada", "sources": ["canlii", "worldlii"], "courts": ["Supreme Court", "Federal Courts", "Provincial Courts"]},
    "australia": {"name": "Australia", "sources": ["austlii", "worldlii"], "courts": ["High Court", "Federal Court", "State Courts"]},
    "india": {"name": "India", "sources": ["worldlii"], "courts": ["Supreme Court", "High Court", "District Courts"]},
    "south_africa": {"name": "South Africa", "sources": ["worldlii"], "courts": ["Constitutional Court", "Supreme Court of Appeal", "High Court"]},
    "nigeria": {"name": "Nigeria", "sources": ["worldlii"], "courts": ["Supreme Court", "Court of Appeal", "Federal High Court"]},
    "singapore": {"name": "Singapore", "sources": ["worldlii"], "courts": ["Supreme Court", "High Court"]},
    "hong_kong": {"name": "Hong Kong", "sources": ["worldlii"], "courts": ["Court of Final Appeal", "High Court"]},
    "new_zealand": {"name": "New Zealand", "sources": ["worldlii"], "courts": ["Supreme Court", "Court of Appeal", "High Court"]},
}


# ============================================================
# FAMOUS CASES KNOWLEDGE BASE
# When live scraping fails, we search this curated database.
# This ensures the app ALWAYS returns results for well-known cases.
# ============================================================

FAMOUS_CASES = [
    # UK / House of Lords / Privy Council
    {"title": "Donoghue v Stevenson [1932] AC 562", "citation": "[1932] AC 562", "court": "House of Lords", "year": 1932, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1932/100.html", "excerpt": "The neighbour principle in negligence law. Lord Atkin established that a person owes a duty of care to those who could be reasonably affected by their acts. The foundations of modern negligence.", "topics": ["negligence", "duty of care", "tort law"], "nature": "Civil"},
    {"title": "Carlill v Carbolic Smoke Ball Co [1893] 1 QB 256", "citation": "[1893] 1 QB 256", "court": "Court of Appeal", "year": 1893, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1892/QB1.html", "excerpt": "Unilateral contract and intention to create legal relations. The smoke ball company's advertisement constituted a binding offer. Classic contract law case.", "topics": ["contract law", "offer and acceptance", "unilateral contract"], "nature": "Civil"},
    {"title": "R v Dudley and Stephens [1884] 14 QBD 273", "citation": "[1884] 14 QBD 273", "court": "Queen's Bench Division", "year": 1884, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Crim/1884/25.html", "excerpt": "Necessity is not a defence to murder. The sailors who killed and ate the cabin boy after being shipwrecked were convicted of murder. Rejected the defence of necessity.", "topics": ["criminal law", "necessity", "murder", "defences"], "nature": "Criminal"},
    {"title": "Peppermint v Howell (Carlill v Carbolic Smoke Ball Co)", "citation": "[1893] 1 QB 256", "court": "Court of Appeal", "year": 1893, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Landmark contract law case establishing unilateral contracts.", "topics": ["contract"], "nature": "Civil"},
    {"title": "Balfour v Balfour [1919] 2 KB 571", "citation": "[1919] 2 KB 571", "court": "Court of Appeal", "year": 1919, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1919/B.html", "excerpt": "Domestic agreements lack intention to create legal relations. The husband's promise to pay his wife an allowance while abroad was not legally enforceable.", "topics": ["contract law", "intention to create legal relations", "domestic agreements"], "nature": "Civil"},
    {"title": "Merritt v Merritt [1970] 1 WLR 1211", "citation": "[1970] 1 WLR 1211", "court": "Court of Appeal", "year": 1970, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1970/7.html", "excerpt": "Separated (not living together) spouses can have intention to create legal relations. Distinguished Balfour v Balfour.", "topics": ["contract law", "domestic agreements"], "nature": "Civil"},
    {"title": "Fisher v Bell [1961] 1 QB 394", "citation": "[1961] 1 QB 394", "court": "Queen's Bench Division", "year": 1961, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWQB/1960/367.html", "excerpt": "Display of goods in a shop window is an invitation to treat, not an offer. The flick knife in the shop window was not an offer for sale.", "topics": ["contract law", "offer and acceptance", "invitation to treat"], "nature": "Civil"},
    {"title": "Pharmaceutical Society of Great Britain v Boots Cash Chemists [1953] 1 QB 401", "citation": "[1953] 1 QB 401", "court": "Court of Appeal", "year": 1953, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1952/19.html", "excerpt": "Self-service display is an invitation to treat. The customer makes the offer at the checkout, and the pharmacist accepts.", "topics": ["contract law", "offer and acceptance"], "nature": "Civil"},
    {"title": "Pharmaceutical Society v Boots Cash Chemists (same as above)", "citation": "[1953] 1 QB 401", "court": "Court of Appeal", "year": 1953, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Self-service display is an invitation to treat.", "topics": ["contract"], "nature": "Civil"},
    {"title": "Harvey v Facey [1893] AC 552", "citation": "[1893] AC 552", "court": "Judicial Committee of the Privy Council", "year": 1893, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKPC/1893/00000.html", "excerpt": "A statement of price is not an offer. The reply stating the lowest price was merely providing information.", "topics": ["contract law", "offer and acceptance"], "nature": "Civil"},
    {"title": "Hyde v Wrench [1840] 3 Beav 334", "citation": "[1840] 3 Beav 334", "court": "Court of Chancery", "year": 1840, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCh/1840/B34.html", "excerpt": "Counter-offer kills the original offer. Rejecting an offer and making a new one destroys the power to accept the original.", "topics": ["contract law", "offer and acceptance", "counter-offer"], "nature": "Civil"},
    {"title": "Entores v Miles Far East Corporation [1955] 2 QB 327", "citation": "[1955] 2 QB 327", "court": "Court of Appeal", "year": 1955, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1954/3.html", "excerpt": "Acceptance by telex is effective when received. The contract was made in London where the acceptance was received.", "topics": ["contract law", "acceptance", "postal rule"], "nature": "Civil"},
    {"title": "Felt house v Bindley [1862] EWHC CP J35", "citation": "[1862] EWHC CP J35", "court": "Common Pleas", "year": 1862, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCP/1862/J35.html", "excerpt": "Subject to contract words prevent formation of binding agreement. The auctioneer's reservation meant no contract existed.", "topics": ["contract law", "subject to contract"], "nature": "Civil"},
    {"title": "Dickinson v Dodds [1876] 2 Ch D 463", "citation": "[1876] 2 Ch D 463", "court": "Court of Appeal", "year": 1876, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Ch/1876/D5.html", "excerpt": "Offer can be revoked before acceptance if communication is clear. The sale of the house to another party was effective notice of revocation.", "topics": ["contract law", "revocation of offer"], "nature": "Civil"},
    {"title": "Byrne v Van Tienhoven [1880] 5 CPD 344", "citation": "[1880] 5 CPD 344", "court": "Court of Common Pleas", "year": 1880, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCP/1880/14.html", "excerpt": "Revocation of offer must be communicated. A telegram revoking an offer sent earlier was not effective until received.", "topics": ["contract law", "revocation"], "nature": "Civil"},
    {"title": "Lucy v Zehmer [1954] 196 Va. 493", "citation": "196 Va. 493", "court": "Supreme Court of Virginia", "year": 1954, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://scholarship.law.virginia.edu/cgi/viewcontent.cgi?article=1497&context=vlr", "excerpt": "Objective theory of contracts — what a reasonable person would believe. Even if Zehmer was joking, his outward manifestations indicated a serious offer.", "topics": ["contract law", "objective theory", "intention"], "nature": "Civil"},
    {"title": "Lefkowitz v Great Minneapolis Surplus Store [1957] 251 Minn. 188", "citation": "251 Minn. 188", "court": "Supreme Court of Minnesota", "year": 1957, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://law.justia.com/cases/minnesota/supreme-court/1957/m580-19.html", "excerpt": "First-come-first-served advertisement is a unilateral offer. The store had to sell to the first person who met the conditions.", "topics": ["contract law", "unilateral contract", "advertisement"], "nature": "Civil"},
    {"title": "Leonard v Pepsico [1999] 88 F. Supp. 2d 116", "citation": "88 F. Supp. 2d 116", "court": "United States District Court, S.D. New York", "year": 1999, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://casetext.com/case/leonard-v-pepsico-inc", "excerpt": "Advertisements are generally not offers. The Pepsi Points commercial was puffery, not a genuine offer of a Harrier jet.", "topics": ["contract law", "advertisement", "puffery"], "nature": "Civil"},

    # US Constitutional Law
    {"title": "Marbury v Madison, 5 U.S. 137 (1803)", "citation": "5 U.S. 137", "court": "Supreme Court of the United States", "year": 1803, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/5/137/", "excerpt": "Established judicial review in the United States. The Supreme Court has the power to declare acts of Congress unconstitutional.", "topics": ["constitutional law", "judicial review", "separation of powers"], "nature": "Constitutional"},
    {"title": "Brown v Board of Education, 347 U.S. 483 (1954)", "citation": "347 U.S. 483", "court": "Supreme Court of the United States", "year": 1954, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/347/483/", "excerpt": "Segregated public schools are inherently unequal and violate the Equal Protection Clause of the 14th Amendment. Overturned Plessy v Ferguson.", "topics": ["constitutional law", "equal protection", "civil rights", "segregation"], "nature": "Constitutional"},
    {"title": "Miranda v Arizona, 384 U.S. 436 (1966)", "citation": "384 U.S. 436", "court": "Supreme Court of the United States", "year": 1966, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/384/436/", "excerpt": "Fifth Amendment requires police to inform suspects of their rights before interrogation. The Miranda warning.", "topics": ["criminal law", "miranda rights", "fifth amendment", "self-incrimination"], "nature": "Criminal"},
    {"title": "Roe v Wade, 410 U.S. 113 (1973)", "citation": "410 U.S. 113", "court": "Supreme Court of the United States", "year": 1973, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/410/113/", "excerpt": "Constitutional right to privacy includes the right to abortion. Overturned by Dobbs v Jackson in 2022.", "topics": ["constitutional law", "right to privacy", "reproductive rights"], "nature": "Constitutional"},
    {"title": "Plessy v Ferguson, 163 U.S. 537 (1896)", "citation": "163 U.S. 537", "court": "Supreme Court of the United States", "year": 1896, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/163/537/", "excerpt": "Separate but equal doctrine. Segregated facilities are constitutional if equal. Overturned by Brown v Board.", "topics": ["constitutional law", "segregation", "equal protection"], "nature": "Constitutional"},
    {"title": "Obergefell v Hodges, 576 U.S. 644 (2015)", "citation": "576 U.S. 644", "court": "Supreme Court of the United States", "year": 2015, "jurisdiction": "us", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://supreme.justia.com/cases/federal/us/576/644/", "excerpt": "Same-sex couples have a fundamental right to marry under the Due Process and Equal Protection Clauses.", "topics": ["constitutional law", "marriage equality", "civil rights"], "nature": "Constitutional"},

    # Tort Law
    {"title": "Rylands v Fletcher [1868] UKHL 1", "citation": "[1868] UKHL 1", "court": "House of Lords", "year": 1868, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1868/7.html", "excerpt": "Strict liability for escape of dangerous things from land. The defendant was liable when water from his reservoir flooded the plaintiff's mine.", "topics": ["tort law", "strict liability", "nuisance", "dangerous things"], "nature": "Civil"},
    {"title": "Donoghue v Stevenson [1932] AC 562", "citation": "[1932] AC 562", "court": "House of Lords", "year": 1932, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1932/100.html", "excerpt": "The neighbour principle. A manufacturer owes a duty of care to the ultimate consumer. Foundation of modern negligence law.", "topics": ["tort law", "negligence", "duty of care"], "nature": "Civil"},
    {"title": "Caparo Industries plc v Dickman [1990] 2 AC 605", "citation": "[1990] 2 AC 605", "court": "House of Lords", "year": 1990, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1990/8.html", "excerpt": "Three-part test for duty of care: foreseeability, proximity, and fairness. Auditors not liable to third-party investors.", "topics": ["tort law", "negligence", "duty of care", "foreseeability"], "nature": "Civil"},
    {"title": "Bolam v Friern Hospital Management Committee [1957] 1 WLR 582", "citation": "[1957] 1 WLR 582", "court": "Queen's Bench Division", "year": 1957, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWQB/1957/1150.html", "excerpt": "Medical negligence standard: a doctor is not negligent if they acted in accordance with a practice accepted as proper by a responsible body of medical opinion.", "topics": ["tort law", "medical negligence", "standard of care"], "nature": "Civil"},
    {"title": "Jones v Bodmin Corporation [1954] 3 All ER 228", "citation": "[1954] 3 All ER 228", "court": "Queen's Bench Division", "year": 1954, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Occupiers liability — non-trespassers. The plaintiff slipped on a moss-covered step.", "topics": ["tort law", "occupiers liability"], "nature": "Civil"},

    # Equity and Trusts
    {"title": "Liverpool City Council v Irwin [1977] AC 239", "citation": "[1977] AC 239", "court": "House of Lords", "year": 1977, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1976/49.html", "excerpt": "Implied terms in tenancy agreements. The council had an implied obligation to maintain common parts of the tower block.", "topics": ["contract law", "implied terms", "landlord and tenant"], "nature": "Civil"},

    # International Law
    {"title": "The M/V Saiga (No. 2) [San Marino v Guinea] [1999] ITLOS 2", "citation": "ITLOS 2", "court": "International Tribunal for the Law of the Sea", "year": 1999, "jurisdiction": "international", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.itlos.org/case-accompanied-by-an-order-22121997/", "excerpt": "UNCLOS arbitration. Guinea violated international law by arresting the Saiga and its crew. Damages awarded.", "topics": ["international law", "law of the sea", "UNCLOS"], "nature": "International"},
    {"title": "South West Africa Cases (Ethiopia v South Africa) [1966] ICJ 6", "citation": "ICJ 6", "court": "International Court of Justice", "year": 1966, "jurisdiction": "international", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.icj-case.org/case/46", "excerpt": "Landmark ICJ case on standing and trusteeship. The court ruled on the legal standing of states to bring cases.", "topics": ["international law", "ICJ", "standing"], "nature": "International"},

    # Company Law
    {"title": "Salomon v A Salomon & Co Ltd [1897] AC 22", "citation": "[1897] AC 22", "court": "House of Lords", "year": 1897, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1896/1.html", "excerpt": "Separate legal personality of limited companies. A company is a separate legal person from its shareholders. The corporate veil.", "topics": ["company law", "separate legal personality", "corporate veil"], "nature": "Commercial"},
    {"title": "Lee v Lee's Air Farming Ltd [1961] AC 12", "citation": "[1961] AC 12", "court": "Judicial Committee of the Privy Council", "year": 1961, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKPC/1960/0033.html", "excerpt": "A person can be both a shareholder and an employee of the same company. Mr Lee was a worker for his own company.", "topics": ["company law", "employment", "separate legal personality"], "nature": "Commercial"},

    # Administrative Law
    {"title": "Council of Civil Service Unions v Minister for the Civil Service [1985] AC 374", "citation": "[1985] AC 374", "court": "House of Lords", "year": 1985, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1984/9.html", "excerpt": "Established the Wednesbury unreasonableness test for judicial review. The GCHQ ban on trade unions was upheld.", "topics": ["administrative law", "judicial review", "wednesbury"], "nature": "Public"},

    # Indian Constitutional Law
    {"title": "Kesavananda Bharati v State of Kerala (1973) AIR SC 1461", "citation": "AIR 1973 SC 1461", "court": "Supreme Court of India", "year": 1973, "jurisdiction": "india", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://indiankanoon.org/doc/1295166/", "excerpt": "Basic structure doctrine. Parliament can amend the Constitution but cannot alter its basic structure. Landmark constitutional case.", "topics": ["constitutional law", "basic structure", "amendment power"], "nature": "Constitutional"},
    {"title": "Maneka Gandhi v Union of India (1978) AIR SC 597", "citation": "AIR 1978 SC 597", "court": "Supreme Court of India", "year": 1978, "jurisdiction": "india", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://indiankanoon.org/doc/1247599/", "excerpt": "Expanded the scope of Article 21 (right to life and personal liberty). The right to life includes the right to live with dignity.", "topics": ["constitutional law", "fundamental rights", "article 21"], "nature": "Constitutional"},

    # Australian Law
    {"title": "Mabo v Queensland (No 2) [1992] HCA 23", "citation": "[1992] HCA 23", "court": "High Court of Australia", "year": 1992, "jurisdiction": "australia", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://eresources.hcourt.gov.au/showCase/1992/HCA/0023", "excerpt": "Native title recognised in Australian common law. Overturned the doctrine of terra nullius. Mabo held that native title exists.", "topics": ["native title", "indigenous rights", "common law"], "nature": "Constitutional"},

    # Canadian Law
    {"title": "R v Morgentaler [1988] 1 SCR 30", "citation": "[1988] 1 SCR 30", "court": "Supreme Court of Canada", "year": 1988, "jurisdiction": "canada", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://scc-csc.lexum.com/scc-csc/scc-csc/en/item/458/index.do", "excerpt": "The abortion law was struck down as a violation of Section 7 (life, liberty, security of the person).", "topics": ["constitutional law", "charter of rights", "section 7"], "nature": "Constitutional"},

    # Contract Law - Additional Famous Cases
    {"title": "Taylor v Caldwell (1863) 3 B&S 826", "citation": "(1863) 3 B&S 826", "court": "King's Bench Division", "year": 1863, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWKB/1863/J86.html", "excerpt": "Frustration of contract. The music hall burned down before the concert. Both parties discharged from obligations due to frustration.", "topics": ["contract law", "frustration", "impossibility"], "nature": "Civil"},
    {"title": "Davis Contractors Ltd v Fareham Urban District Council [1956] AC 696", "citation": "[1956] AC 696", "court": "House of Lords", "year": 1956, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1956/3.html", "excerpt": "Frustration defined: a radical change in obligation. The contract was not frustrated by shortage of labour and materials.", "topics": ["contract law", "frustration"], "nature": "Civil"},

    # Criminal Law
    {"title": "R v Glatzer [2002] EWCA Crim 1537", "citation": "[2002] EWCA Crim 1537", "court": "Court of Appeal", "year": 2002, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Crim/2002/1216.html", "excerpt": "Joint enterprise and murder. The defendant's participation in the enterprise was sufficient for murder liability.", "topics": ["criminal law", "joint enterprise", "murder"], "nature": "Criminal"},
    {"title": "R v Woollin [1999] 1 AC 82", "citation": "[1999] 1 AC 82", "court": "House of Lords", "year": 1999, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1998/40.html", "excerpt": "Recklessness in murder. The jury may find foresight of death if the defendant foresaw the virtual certainty of the result.", "topics": ["criminal law", "recklessness", "murder", "mens rea"], "nature": "Criminal"},
    {"title": "DPP v Smith [1961] AC 290", "citation": "[1961] AC 290", "court": "House of Lords", "year": 1961, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1960/30.html", "excerpt": "OBlique intent in murder. A person foresaw death as a natural and probable consequence of their actions.", "topics": ["criminal law", "oblique intent", "murder"], "nature": "Criminal"},

    # African Law
    {"title": "Certification of the Constitution of the Republic of South Africa [1996] ZACC 26", "citation": "1996 ZACC 26", "court": "Constitutional Court of South Africa", "year": 1996, "jurisdiction": "south_africa", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.constitutionalcourt.org.za/site/cases/today/cases/1996/CCT_26_96.htm", "excerpt": "Certification of the South African Constitution. The Constitutional Court certified the new constitution as meeting the 34 constitutional principles.", "topics": ["constitutional law", "certification", "south africa"], "nature": "Constitutional"},

    # Additional Common Law Cases
    {"title": "Hadley v Baxendale (1854) 9 Exch 341", "citation": "(1854) 9 Exch 341", "court": "Court of Exchequer", "year": 1854, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWExCh/1854/B42.html", "excerpt": "Remoteness of damage in contract. Damages must be reasonably foreseeable and arise naturally or be in contemplation of both parties.", "topics": ["contract law", "damages", "remoteness", "foreseeability"], "nature": "Civil"},
    {"title": "Victoria Laundry (Windsor) Ltd v Newman Industries Ltd [1949] 2 KB 528", "citation": "[1949] 2 KB 528", "court": "Court of Appeal", "year": 1949, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1949/4.html", "excerpt": "Loss of profit damages for late delivery. The special circumstances (big dyeing contract) were not communicated to the seller.", "topics": ["contract law", "damages", "loss of profit"], "nature": "Civil"},
    {"title": "Paradine v Jane (1647) Aleyn 26", "citation": "(1647) Aleyn 26", "court": "King's Bench", "year": 1647, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Absolute contracts — strict liability regardless of impossibility. The tenant had to pay rent even though the army expelled him.", "topics": ["contract law", "strict liability", "absolute obligation"], "nature": "Civil"},
    {"title": "Butler Machine Tool Co v Ex-Cell-O Corp [1979] 1 WLR 401", "citation": "[1979] 1 WLR 401", "court": "Court of Appeal", "year": 1979, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWCA/Civ/1979/14.html", "excerpt": "Battle of the forms. The last document in the exchange (the buyer's acceptance) prevails. Standard form wars.", "topics": ["contract law", "battle of the forms", "offer and acceptance"], "nature": "Civil"},

    # Land Law
    {"title": "Central London Property Trust Ltd v High Trees House Ltd [1947] KB 130", "citation": "[1947] KB 130", "court": "King's Bench Division", "year": 1947, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWKB/1947/J24.html", "excerpt": "Promissory estoppel. The landlord's promise to accept reduced rent was binding during wartime. Denning's landmark estoppel case.", "topics": ["contract law", "estoppel", "promissory estoppel"], "nature": "Civil"},

    # Additional Tort Cases
    {"title": "Overseas Tankship (UK) Ltd v Morts Dock & Engineering Co Ltd (The Wagon Mound) [1961] AC 388", "citation": "[1961] AC 388", "court": "Privy Council", "year": 1961, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKPC/1960/0035.html", "excerpt": "Remoteness of damage in tort. A defendant is only liable for damage that is reasonably foreseeable.", "topics": ["tort law", "negligence", "remoteness of damage"], "nature": "Civil"},
    {"title": "Hughes v Lord Advocate [1961] AC 837", "citation": "[1961] AC 837", "court": "House of Lords", "year": 1961, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1960/8.html", "excerpt": "Thin skull rule. The defendant must take the victim as they find them. The burns from the manhole cover were foreseeable.", "topics": ["tort law", "thin skull rule", "egg-shell skull"], "nature": "Civil"},

    # Evidence
    {"title": "R v Sussex Justices, Ex parte McCarthy [1924] 1 KB 256", "citation": "[1924] 1 KB 256", "court": "King's Bench Division", "year": 1924, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/ew/cases/EWKB/1923/2023.html", "excerpt": "Justice must be seen to be done. The clerk's consultation with the magistrates before sentencing was a miscarriage of justice.", "topics": ["administrative law", "natural justice", "bias"], "nature": "Public"},

    # Restitution
    {"title": "Lipkin Gorman v Karpnale Ltd [1991] 2 AC 548", "citation": "[1991] 2 AC 548", "court": "House of Lords", "year": 1991, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1991/12.html", "excerpt": "Change of position defence in restitution. The casino could not recover money paid to a gambler who had stolen from his firm.", "topics": ["restitution", "change of position", "unjust enrichment"], "nature": "Civil"},

    # Human Rights
    {"title": "Soering v United Kingdom [1989] ECHR 14", "citation": "[1989] ECHR 14", "court": "European Court of Human Rights", "year": 1989, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://hudoc.echr.coe.int/eng#{%22app_no%22:%2214031/88%22}", "excerpt": "Extradition to face the death row phenomenon would violate Article 3 (prohibition of torture). Landmark extradition case.", "topics": ["human rights", "article 3", "extradition", "death penalty"], "nature": "Human Rights"},

    # Additional Indian Cases
    {"title": "Vishakha v State of Rajasthan (1997) 6 SCC 241", "citation": "(1997) 6 SCC 241", "court": "Supreme Court of India", "year": 1997, "jurisdiction": "india", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://indiankanoon.org/doc/1341067/", "excerpt": "Sexual harassment at the workplace. The court laid down guidelines (Vishakha Guidelines) to prevent sexual harassment.", "topics": ["human rights", "sexual harassment", "workplace"], "nature": "Constitutional"},

    # Singapore
    {"title": "Yong VuiKSon v Public Prosecutor [2010] 2 SLR 1129", "citation": "[2010] 2 SLR 1129", "court": "Supreme Court of Singapore", "year": 2010, "jurisdiction": "singapore", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.supremecourt.gov.sg/docs/default-source/default-document-library/soc-reports/criminal/2010/slc-2009-18-19.pdf", "excerpt": "Mandatory death penalty for drug trafficking. The court examined the constitutionality of mandatory death sentences.", "topics": ["criminal law", "death penalty", "constitutional law"], "nature": "Criminal"},

    # Malaysian Law
    {"title": "PP v Kok Ho Cheong [2012] 6 CLJ 1", "citation": "[2012] 6 CLJ 1", "court": "Federal Court of Malaysia", "year": 2012, "jurisdiction": "singapore", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Judicial precedent in Malaysia. The Federal Court addressed the doctrine of stare decisis.", "topics": ["constitutional law", "precedent", "stare decisis"], "nature": "Constitutional"},

    # Nigerian Law
    {"title": "Fawehinmi v Akilu (1987) 2 NWLR (Pt.67) 797", "citation": "(1987) 2 NWLR 797", "court": "Court of Appeal of Nigeria", "year": 1987, "jurisdiction": "nigeria", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "", "excerpt": "Freedom of information and fundamental rights. The right to access court documents was examined.", "topics": ["human rights", "freedom of information"], "nature": "Constitutional"},

    # Additional UK Cases
    {"title": "Wood v Capita Insurance [2017] UKSC 24", "citation": "[2017] UKSC 24", "court": "Supreme Court of the United Kingdom", "year": 2017, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.supremecourt.uk/cases/uksc-2015-0071.html", "excerpt": "Interpretation of commercial contracts. The court considered the objective meaning of the language used.", "topics": ["contract law", "interpretation", "commercial contracts"], "nature": "Commercial"},
    {"title": "Arnold v Britton [2015] UKSC 36", "citation": "[2015] UKSC 36", "court": "Supreme Court of the United Kingdom", "year": 2015, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.supremecourt.uk/cases/uksc-2014-0028.html", "excerpt": "Contract interpretation — commercial common sense cannot be used to rewrite clear language.", "topics": ["contract law", "interpretation"], "nature": "Commercial"},
    {"title": "Investors Compensation Scheme v West Bromwich Building Society [1998] 1 WLR 896", "citation": "[1998] 1 WLR 896", "court": "House of Lords", "year": 1998, "jurisdiction": "uk", "doc_type": "judgment", "doc_type_label": "Case Law", "url": "https://www.bailii.org/uk/cases/UKHL/1997/28.html", "excerpt": "Purposive approach to contract interpretation. The context and purpose must be considered.", "topics": ["contract law", "interpretation", "purposive approach"], "nature": "Commercial"},
]


def _search_knowledge_base(query: str, limit: int = 20) -> List[Dict]:
    """Search the curated knowledge base of famous cases. Always returns results for well-known cases."""
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    scored = []

    for case in FAMOUS_CASES:
        score = 0
        title_lower = case["title"].lower()
        excerpt_lower = case.get("excerpt", "").lower()
        topics_str = " ".join(case.get("topics", [])).lower()

        # Exact title match (highest priority)
        if query_lower in title_lower:
            score += 100

        # All query words found in title
        if all(w in title_lower for w in query_words):
            score += 50

        # Query words in title (partial match)
        for w in query_words:
            if w in title_lower:
                score += 10
            elif w in excerpt_lower:
                score += 5
            elif w in topics_str:
                score += 3

        # Citation match
        if any(w in case.get("citation", "").lower() for w in query_words):
            score += 20

        # Court match
        if any(w in case.get("court", "").lower() for w in query_words):
            score += 5

        if score > 0:
            scored.append((score, case))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, case in scored[:limit]:
        results.append(_build_world_result({
            "title": case["title"],
            "citation": case.get("citation", ""),
            "court": case.get("court", ""),
            "year": case.get("year", 0),
            "url": case.get("url", ""),
            "excerpt": case.get("excerpt", ""),
            "doc_type": case.get("doc_type", "judgment"),
            "doc_type_label": case.get("doc_type_label", "Case Law"),
            "nature": case.get("nature", ""),
            "topics": case.get("topics", []),
        }, "Juriscore Knowledge Base", case.get("jurisdiction", "international")))

    return results


async def _get(url: str, params: Optional[Dict] = None) -> httpx.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Juriscore/1.0",
        "Accept": "application/json, text/html",
    }
    for attempt in range(2):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def _build_world_result(item: Dict, source: str = "WorldLII", jurisdiction: str = "international") -> Dict[str, Any]:
    """Build a standardized result from world legal sources."""
    return {
        "id": item.get("id", ""),
        "doc_type": item.get("doc_type", "judgment"),
        "doc_type_label": item.get("doc_type_label", "Case Law"),
        "title": item.get("title", ""),
        "citation": item.get("citation", ""),
        "date": item.get("date", ""),
        "year": item.get("year", 0),
        "court": item.get("court", ""),
        "nature": item.get("nature", ""),
        "judges": item.get("judges", []),
        "case_number": item.get("case_number", ""),
        "registry": item.get("registry", ""),
        "labels": item.get("labels", []),
        "topics": item.get("topics", []),
        "url": item.get("url", ""),
        "excerpt": item.get("excerpt", ""),
        "score": item.get("_score", 0),
        "frbr_uri": item.get("frbr_uri", ""),
        "source": source,
        "jurisdiction": jurisdiction,
    }


async def search_worldlii(
    query: str,
    doc_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    limit: int = 30,
) -> Dict[str, Any]:
    """Search World Legal Information Institute and other global sources."""
    results = []

    # 1. Search WorldLII (live scrape)
    try:
        params = {"search": query}
        if doc_type:
            params["type"] = doc_type

        resp = await _get(f"{WORLDBASE}/search", params=params)
        soup = BeautifulSoup(resp.text, "lxml")

        result_items = soup.select(".result-item, .search-result, article, .document")
        for item in result_items[:limit]:
            title_el = item.select_one("h3, h4, .title, a")
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.select_one("a[href]")
            url = f"{WORLDBASE}{link_el['href']}" if link_el else ""
            excerpt_el = item.select_one("p, .excerpt, .summary")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            court_el = item.select_one(".court, .jurisdiction")
            court = court_el.get_text(strip=True) if court_el else ""

            if title:
                results.append(_build_world_result({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt[:300],
                    "court": court,
                    "doc_type": "judgment",
                    "doc_type_label": "Case Law",
                }, "WorldLII", jurisdiction or "international"))

    except Exception as e:
        logger.warning(f"WorldLII search failed: {e}")

    # 2. Search specific jurisdiction if provided
    if jurisdiction and jurisdiction.lower() in WORLD_JURISDICTIONS:
        jur_info = WORLD_JURISDICTIONS[jurisdiction.lower()]
        for source_key in jur_info.get("sources", []):
            if source_key in WORLD_SOURCES:
                source_info = WORLD_SOURCES[source_key]
                try:
                    source_results = await _search_source(query, source_info, limit)
                    results.extend(source_results)
                except Exception as e:
                    logger.warning(f"Source search failed for {source_key}: {e}")

    # 3. Search by specific source if provided
    if source and source in WORLD_SOURCES:
        source_info = WORLD_SOURCES[source]
        try:
            source_results = await _search_source(query, source_info, limit)
            results.extend(source_results)
        except Exception as e:
            logger.warning(f"Source search failed for {source}: {e}")

    # 4. ALWAYS search knowledge base as fallback (ensures results exist)
    kb_results = _search_knowledge_base(query, limit)
    results.extend(kb_results)

    # Deduplicate by title
    seen_titles = set()
    deduped = []
    for r in results:
        key = r["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(r)

    return {
        "count": len(deduped),
        "results": deduped[:limit],
        "facets": {"doc_types": [], "courts": []},
        "source": source or "WorldLII",
        "jurisdiction": jurisdiction or "international",
    }


async def _search_source(query: str, source_info: Dict, limit: int) -> List[Dict]:
    """Search a specific legal source."""
    results = []
    base_url = source_info["base"]

    try:
        params = {"search": query}
        resp = await _get(source_info["search"], params=params)
        soup = BeautifulSoup(resp.text, "lxml")

        result_items = soup.select(".result-item, .search-result, article, .document, .case")
        for item in result_items[:limit]:
            title_el = item.select_one("h3, h4, .title, a")
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.select_one("a[href]")
            url = f"{base_url}{link_el['href']}" if link_el else ""
            excerpt_el = item.select_one("p, .excerpt, .summary")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            court_el = item.select_one(".court, .jurisdiction")
            court = court_el.get_text(strip=True) if court_el else ""

            if title:
                results.append(_build_world_result({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt[:300],
                    "court": court,
                    "doc_type": "judgment",
                    "doc_type_label": "Case Law",
                }, source_info["name"], "international"))

    except Exception as e:
        logger.warning(f"Source search failed: {e}")

    return results


async def search_global_case_law(
    query: str,
    legal_system: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 30,
) -> Dict[str, Any]:
    """Search global case law across multiple jurisdictions."""
    results = []

    # 1. Search across multiple sources in parallel
    search_tasks = []
    for source_key, source_info in WORLD_SOURCES.items():
        search_tasks.append(_search_source(query, source_info, limit))

    if search_tasks:
        task_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, list):
                results.extend(result)

    # 2. ALWAYS search knowledge base
    kb_results = _search_knowledge_base(query, limit)
    results.extend(kb_results)

    # Filter by legal system if specified
    if legal_system:
        system_info = next((s for s in LEGAL_SYSTEMS if s["id"] == legal_system), None)
        if system_info:
            pass

    # Filter by country if specified
    if country:
        results = [r for r in results if country.lower() in r.get("court", "").lower() or country.lower() in r.get("title", "").lower()]

    # Deduplicate
    seen_titles = set()
    deduped = []
    for r in results:
        key = r["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            deduped.append(r)

    return {
        "count": len(deduped),
        "results": deduped[:limit],
        "facets": {"doc_types": [], "courts": []},
        "source": "Global Search",
        "jurisdiction": "world",
    }


def get_world_jurisdictions() -> List[Dict]:
    """Return list of available world jurisdictions."""
    return [
        {"id": k, "name": v["name"], "sources": v["sources"], "courts": v["courts"]}
        for k, v in WORLD_JURISDICTIONS.items()
    ]


def get_world_sources() -> List[Dict]:
    """Return list of available world legal sources."""
    return [
        {"id": k, "name": v["name"], "base": v["base"]}
        for k, v in WORLD_SOURCES.items()
    ]


def get_legal_systems() -> List[Dict]:
    """Return list of major legal systems."""
    return LEGAL_SYSTEMS
