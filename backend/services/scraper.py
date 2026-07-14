import os
import httpx
import asyncio
import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

BASE_URL = os.getenv("KENYALAW_BASE", "https://www.kenyalaw.org")
SEMAPHORE = asyncio.Semaphore(2)

DEMO_CASES = [
    {
        "title": "Marbury v. Madison",
        "citation": "5 U.S. (1 Cranch) 137 (1803)",
        "court": "Supreme Court",
        "year": 1803,
        "subject_tags": ["Constitutional Law", "Judicial Review"],
        "full_text": "Marbury v. Madison, 5 U.S. (1 Cranch) 137 (1803), was a landmark U.S. Supreme Court case that established the principle of judicial review. William Marbury petitioned the Supreme Court for a writ of mandamus compelling Secretary of State James Madison to deliver his commission as justice of the peace. Chief Justice John Marshall held that while Marbury had a right to his commission, the Supreme Court lacked original jurisdiction to issue the writ, as Section 13 of the Judiciary Act of 1789 unconstitutionally expanded the Court's original jurisdiction. The case established that the Supreme Court has the authority to declare acts of Congress unconstitutional.",
        "judges": ["John Marshall", "William Cushing", "John Blair"],
    },
    {
        "title": "Carlill v Carbolic Smoke Ball Co",
        "citation": "[1893] 1 QB 256",
        "court": "Court of Appeal",
        "year": 1893,
        "subject_tags": ["Contract Law", "Offer and Acceptance"],
        "full_text": "The Carbolic Smoke Ball Company placed an advertisement claiming that their product would prevent influenza. Mrs Carlill used the product as directed but contracted influenza. She sued for the 100 pounds reward promised in the advertisement. The Court of Appeal held that the advertisement constituted a unilateral offer to the world at large, and Mrs Carlill's use of the smoke ball constituted acceptance. The deposit of 1000 pounds in a bank showed the company's sincerity, making it a serious offer rather than mere puffery.",
        "judges": ["Lord Lindley", "Lord Bowen", "Kay LJ"],
    },
    {
        "title": "Donoghue v Stevenson",
        "citation": [1932] AC 562,
        "court": "House of Lords",
        "year": 1932,
        "subject_tags": ["Tort Law", "Negligence"],
        "full_text": "Mrs Donoghue drank ginger beer from a opaque bottle at a cafe in Paisley, Scotland. When more ginger beer was poured, a decomposed snail floated out. She suffered nervous shock and gastro-enteritis. The House of Lords held that the manufacturer owed a duty of care to the ultimate consumer, even in the absence of a contract. Lord Atkin formulated the neighbour principle: you must take reasonable care to avoid acts or omissions which you can reasonably foresee would be likely to injure your neighbour.",
        "judges": ["Lord Atkin", "Lord Macmillan", "Lord Thankerton"],
    },
    {
        "title": "R v. Morrison",
        "citation": "2023 SCC 14",
        "court": "Supreme Court",
        "year": 2023,
        "subject_tags": ["Criminal Law", "Privacy"],
        "full_text": "A landmark decision clarifying the scope of reasonable expectation of privacy in digital communications accessed through third-party servers. The respondent Morrison was investigated for alleged involvement in a narcotics trafficking ring. Law enforcement intercepted textual communications stored on a secure, encrypted third-party server. The police accessed these records without a specific warrant, relying on a general production order. The Court held that an individual retains a reasonable expectation of privacy in digital communications stored on third-party servers, provided they have taken reasonable steps to ensure confidentiality.",
        "judges": ["Chief Justice Wagner", "Justice Moldaver", "Justice Karakatsanis"],
    },
    {
        "title": "Palsgraf v. Long Island Railroad Co.",
        "citation": "248 N.Y. 339",
        "court": "Court of Appeals",
        "year": 1928,
        "subject_tags": ["Tort Law", "Negligence", "Proximate Cause"],
        "full_text": "Mrs Palsgraf was standing on a railroad platform when guards on a moving train attempted to help a passenger board. The passenger's package, which contained fireworks, was knocked onto the tracks and exploded. The shock caused scales at the other end of the platform to fall on Mrs Palsgraf. The Court of Appeals held that the railroad was not liable because the harm to Mrs Palsgraf was not a foreseeable consequence of the guards' negligence. Judge Cardozo established the principle that duty is owed only to those within the zone of foreseeable danger.",
        "judges": ["Cardozo CJ", "Andrews J"],
    },
]

DEMO_STATUTES = [
    {
        "title": "Sale of Goods Act",
        "citation": "Cap 31, Laws of Kenya",
        "cap_number": "Cap 31",
        "full_text": "An Act to consolidate the law relating to the sale of goods.\n\nSection 1 - Short title\nThis Act may be cited as the Sale of Goods Act.\n\nSection 2 - Interpretation\nGoods means every kind of movable property other than money and choses in action.\n\nSection 3 - Capacity to buy and sell\nCapacity to buy and sell is regulated by the general law relating to capacity to contract.",
    },
    {
        "title": "Law of Contract Act",
        "citation": "Cap 23, Laws of Kenya",
        "cap_number": "Cap 23",
        "full_text": "An Act to amend and consolidate the law relating to contracts.\n\nSection 2 - Formation of contract\nA contract is formed by offer and acceptance.\n\nSection 3 - Free consent\nConsent is free when it is not caused by coercion, undue influence, fraud, misrepresentation or mistake.",
    },
    {
        "title": "Penal Code",
        "citation": "Cap 63, Laws of Kenya",
        "cap_number": "Cap 63",
        "full_text": "An Act to establish a Penal Code.\n\nPart II - General provisions\nSection 4 - Classification of offences\nOffences are classified as felonies and misdemeanours.",
    },
]


async def _get(url: str, params: Optional[Dict] = None) -> httpx.Response:
    headers = {"User-Agent": "Juriscore/1.0 (student research bot; academic use)"}
    for attempt in range(2):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Scrape attempt {attempt+1} failed for {url}: {e}")
                await asyncio.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after retries")


async def scrape_case(url: str) -> Dict[str, Any]:
    try:
        resp = await _get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one("h1, .case-title, title")
        title = title_el.get_text(strip=True) if title_el else ""
        citation_el = soup.select_one(".citation")
        citation = citation_el.get_text(strip=True) if citation_el else ""
        court_el = soup.select_one(".court")
        court = court_el.get_text(strip=True) if court_el else ""
        year = 0
        m = re.search(r"(19|20)\d{2}", citation or title or "")
        if m:
            year = int(m.group(0))
        judges: List[str] = []
        judges_tag = soup.select_one(".judges")
        if judges_tag:
            judges = [j.strip() for j in judges_tag.get_text(separator=",").split(",") if j.strip()]
        body = soup.select_one(".body, .case-body, #content, article")
        full_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
        return {"title": title, "citation": citation, "court": court, "year": year, "judges": judges, "full_text": full_text, "cases_cited": [], "subject_tags": []}
    except Exception as e:
        logger.warning(f"Failed to scrape case {url}: {e}")
        return {"title": "", "citation": "", "court": "", "year": 0, "judges": [], "full_text": "", "cases_cited": [], "subject_tags": []}


async def search_cases(query: Optional[str], filters: Optional[Dict] = None) -> List[Dict]:
    # Try scraping first
    try:
        params = {"q": query or "", "format": "json"}
        if filters:
            for k, v in filters.items():
                if v:
                    params[k] = v
        resp = await _get(urljoin(BASE_URL, "/search"), params=params)
        try:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"External search failed: {e}")

    # Fallback to demo data filtered by query
    results = []
    q = (query or "").lower()
    for case in DEMO_CASES:
        matches = True
        if q and q not in case["title"].lower() and q not in case["full_text"].lower():
            matches = False
        if filters:
            court = filters.get("court", "")
            subject = filters.get("subject", "")
            if court and case["court"].lower() != court.lower():
                matches = False
            if subject and subject.lower() not in [t.lower() for t in case.get("subject_tags", [])]:
                matches = False
        if matches:
            results.append(case)
    return results


async def scrape_statute(act_id: str) -> Dict[str, Any]:
    try:
        url = f"{BASE_URL}/lex/actview.xql?actid={quote_plus(act_id)}"
        resp = await _get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one("h1, .title, title")
        title = title_el.get_text(strip=True) if title_el else act_id
        body = soup.select_one(".body, #content, article")
        full_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
        return {"act_id": act_id, "title": title, "full_text": full_text}
    except Exception as e:
        logger.warning(f"Failed to scrape statute {act_id}: {e}")
        for s in DEMO_STATUTES:
            if act_id.lower() in s["title"].lower() or act_id.lower() in s.get("cap_number", "").lower():
                return {"act_id": act_id, "title": s["title"], "full_text": s["full_text"]}
        return {"act_id": act_id, "title": act_id, "full_text": "Statute text unavailable."}


async def scrape_constitution() -> Dict[str, Any]:
    try:
        url = f"{BASE_URL}/lex/actview.xql?actid=Const2010"
        resp = await _get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one("h1, .title, title")
        title = title_el.get_text(strip=True) if title_el else "Constitution of Kenya 2010"
        body = soup.select_one(".body, #content, article")
        full_text = body.get_text(separator="\n\n", strip=True) if body else soup.get_text(separator="\n\n", strip=True)
        if len(full_text) > 100:
            return {"title": title, "full_text": full_text}
    except Exception as e:
        logger.warning(f"Failed to scrape constitution: {e}")

    # Fallback to embedded constitution text
    return {"title": "Constitution of Kenya 2010", "full_text": CONSTITUTION_TEXT}


CONSTITUTION_TEXT = """PREAMBLE
WE, THE PEOPLE OF KENYA:
ACKNOWLEDGING the supremacy of the Almighty God and all authority and sovereignty belonging to Him alone and faithfully exercising our trust in Him;
RECOGNISING the aspirations of all Kenyans for a government based on the essential values of human rights, equality, freedom, democracy, social justice and the rule of law;
EXERCISING our sovereign and inalienable right to determine the form of governance of our country and having fully participated in the preparation of this Constitution, do hereby adopt, enact and give to ourselves this Constitution.

CHAPTER ONE - THE REPUBLIC
Article 1 - Sovereignty of the people
(1) All sovereign power belongs to the people of Kenya and shall be exercised in accordance with this Constitution.
(2) The people may exercise their sovereign power directly or through their democratically elected representatives.

Article 2 - Supremacy of this Constitution
(1) This Constitution is the supreme law of the Republic and binds all persons and all State organs at both levels of government.
(2) No person may claim or exercise State authority except as authorised by this Constitution.

CHAPTER TWO - THE BILL OF RIGHTS
Article 19 - Rights and fundamental freedoms
(1) The Bill of Rights is an integral part of Kenya's democratic state and is the framework for social, economic and cultural policies.
(2) The rights and fundamental freedoms in the Bill of Rights belong to each individual and are not granted by the State.

Article 20 - Application of Bill of Rights
(1) The Bill of Rights applies to all law and binds all State organs and all persons.
(2) Every person shall enjoy all the rights and fundamental freedoms in the Bill of Rights to the fullest extent consistent with the nature of the right or fundamental freedom.

Article 21 - Implementation of rights and fundamental freedoms
(1) It is a fundamental duty of the State and every State organ to respect, protect, promote and fulfil the rights and fundamental freedoms in the Bill of Rights.

CHAPTER THREE - CITIZENSHIP
Article 16 - Citizenship by birth
A person is a citizen by birth if the person is born in Kenya and at the time of the person's birth the father or mother is a citizen of Kenya.

Article 17 - Citizenship by registration
A person may apply to be registered as a citizen if the person has ordinarily resided in Kenya for a continuous period of at least seven years.

CHAPTER FOUR - THE LAND AND ENVIRONMENT
Article 40 - Protection of right to property
(1) Every person has the right, either individually or in association with others, to acquire and own property.
(2) Parliament shall not enact a law that permits the State or any person to arbitrarily deprive a person of property of any description.

CHAPTER FIVE - SOVEREIGNTY OF THE PEOPLE AND SUPREMACY OF THIS CONSTITUTION
Article 1 - Sovereignty of the people
All sovereign power belongs to the people of Kenya and shall be exercised in accordance with this Constitution.

CHAPTER SIX - THE LEGISLATURE
Article 93 - Functions of Parliament
(1) The legislative authority of the Republic is vested in and exercised by Parliament.
(2) Parliament enacts legislation as provided for in this Constitution.

Article 94 - Exercise of legislative authority
(1) The legislative authority of the Republic is vested in and exercises by Parliament.

CHAPTER SEVEN - THE EXECUTIVE
Article 130 - National Executive
(1) The executive authority of the Republic is vested in the President.
(2) The President exercises the executive authority with the assistance of the Cabinet.

Article 131 - Authority of the President
(1) The President is the Head of State and Government and exercises the executive authority of the Republic.

CHAPTER EIGHT - THE JUDICIARY
Article 159 - Judicial authority
(1) Judicial authority is derived from the people of Kenya and vests in, and is exercised by, the courts and tribunals.

Article 160 - Independence of the Judiciary
(1) In the exercise of judicial authority, the Judiciary, as constituted by Article 161, shall be subject only to this Constitution and the law and shall not be subject to the control or direction of any person or authority.

CHAPTER NINE - DEVOLVED GOVERNMENT
Article 174 - Objects of devolution
The objects of the devolution of government are to promote democratic and accountable exercise of power; to foster national unity; to give recognition to the right of communities to manage their own affairs.

Article 175 - Principles of devolved government
Authority assigned to a county government is to be exercised in accordance with this Constitution.

CHAPTER TEN - LEADERSHIP AND INTEGRITY
Article 73 - Principles of leadership
(1) Authority assigned to a State officer is a public trust to be exercised in a manner that is consistent with the purposes and objects of this Constitution.

CHAPTER ELEVEN - THE PUBLIC SERVICE
Article 232 - Values and principles of public service
The values and principles of public service include high standards of professional ethics; efficient, effective and economic use of resources."""

