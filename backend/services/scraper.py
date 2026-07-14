import os
import httpx
import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

KENYALAW_BASE = "https://kenyalaw.org"
KENYALAW_SEARCH_API = f"{KENYALAW_BASE}/search/api/documents/"
SEMAPHORE = asyncio.Semaphore(3)

DOC_TYPE_MAP = {
    "judgment": "Case Law",
    "legislation": "Legislation",
    "gazette": "Gazette",
    "bill": "Bill",
    "generic_document": "Publication",
    "journal": "Journal",
    "causelist": "Cause List",
}

# Reverse map for fuzzy matching against kenyalaw's actual doc_type values
DOC_TYPE_ALIASES = {
    "case law": "judgment", "case": "judgment", "cases": "judgment",
    "law": "legislation", "act": "legislation", "acts": "legislation",
    "statute": "legislation", "statutes": "legislation",
    "gazette": "gazette", "gazettes": "gazette",
    "bill": "bill", "bills": "bill",
    "publication": "generic_document", "publications": "generic_document",
    "journal": "journal", "journals": "journal",
    "cause list": "causelist", "causelists": "causelist",
}


def _normalize_doc_type(raw: str) -> str:
    """Normalize a doc_type string to match kenyalaw.org's values."""
    lower = raw.lower().strip()
    if lower in DOC_TYPE_MAP or lower in DOC_TYPE_ALIASES:
        return DOC_TYPE_ALIASES.get(lower, lower)
    return lower


async def _get(url: str, params: Optional[Dict] = None) -> httpx.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Juriscore/1.0",
        "Accept": "application/json, text/html",
    }
    for attempt in range(2):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {url}: {e}")
                await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}")


def _build_result(item: Dict) -> Dict[str, Any]:
    doc_type = item.get("doc_type", "unknown")
    frbr_uri = item.get("expression_frbr_uri", "")
    url = f"{KENYALAW_BASE}{frbr_uri}" if frbr_uri else ""

    case_numbers = item.get("case_number", [])
    case_number = case_numbers[0] if case_numbers else ""

    pages = item.get("pages", [])
    excerpt = ""
    if pages:
        highlights = pages[0].get("highlight", {}).get("pages.body", [])
        if highlights:
            excerpt = highlights[0]

    return {
        "id": item.get("id", ""),
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPE_MAP.get(doc_type, doc_type),
        "title": item.get("title", ""),
        "citation": item.get("citation", ""),
        "date": item.get("date", ""),
        "year": item.get("year", 0),
        "court": item.get("court", ""),
        "nature": item.get("nature", ""),
        "judges": item.get("judges", []),
        "case_number": case_number,
        "registry": item.get("registry", ""),
        "labels": item.get("labels", []),
        "topics": item.get("topic_path_names", []),
        "url": url,
        "excerpt": excerpt,
        "score": item.get("_score", 0),
        "frbr_uri": frbr_uri,
    }


async def search_kenyalaw(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    page: int = 1,
    ordering: str = "-score",
    limit: int = 50,
) -> Dict[str, Any]:
    """Search kenyalaw.org with AI-powered query correction and fuzzy filter matching."""
    from services.ai_service import (
        rewrite_search_query, rank_search_results,
        fuzzy_match_court, fuzzy_match_doc_type,
    )

    # Step 1: AI query rewriting (fix misspellings, expand terms)
    query_info = await rewrite_search_query(query)
    search_query = query_info["query"]
    suggestions = query_info.get("suggestions", [])
    query_corrected = query_info.get("corrected", False)

    logger.info(f"AI query rewrite: '{query}' → '{search_query}' (corrected={query_corrected})")

    # Step 2: Fuzzy match doc_type filter
    matched_doc_type = None
    if doc_type and doc_type != "all":
        matched_doc_type = _normalize_doc_type(doc_type)
        # If not a known type, try fuzzy matching
        if matched_doc_type not in DOC_TYPE_MAP:
            fuzzy = fuzzy_match_doc_type(doc_type)
            if fuzzy:
                matched_doc_type = fuzzy
                logger.info(f"Fuzzy doc_type match: '{doc_type}' → '{matched_doc_type}'")

    # Step 3: Fuzzy match court filter
    matched_court = None
    if court and court != "all":
        matched_court = court  # Keep original for substring matching
        fuzzy_court = fuzzy_match_court(court)
        if fuzzy_court:
            matched_court = fuzzy_court
            logger.info(f"Fuzzy court match: '{court}' → '{matched_court}'")

    # Step 4: Execute search with corrected query
    params = {
        "search": search_query,
        "page": str(page),
        "ordering": ordering,
    }

    try:
        resp = await _get(KENYALAW_SEARCH_API, params=params)
        data = resp.json()
    except Exception as e:
        logger.error(f"kenyalaw.org search failed: {e}")
        return {
            "count": 0, "results": [], "facets": {},
            "query_corrected": query_corrected, "original_query": query,
            "corrected_query": search_query, "suggestions": suggestions,
        }

    all_items = data.get("results", [])
    total_count = data.get("count", 0)

    # Step 5: Client-side filtering with fuzzy matching
    results = []
    for item in all_items:
        r = _build_result(item)

        if matched_doc_type and matched_doc_type != "all" and r["doc_type"] != matched_doc_type:
            continue

        if matched_court and matched_court != "all":
            if matched_court.lower() not in (r["court"] or "").lower():
                continue

        results.append(r)
        if len(results) >= limit:
            break

    # Step 6: AI-powered result ranking (only if we have results and query was non-trivial)
    if results and len(results) > 3 and query.strip():
        results = await rank_search_results(query, results, limit)

    # Extract facets
    facets_raw = data.get("facets", {})
    facets = {}
    doc_type_facet = facets_raw.get("_filter_doc_type", {}).get("doc_type", {}).get("buckets", [])
    facets["doc_types"] = [{"key": f["key"], "count": f["doc_count"]} for f in doc_type_facet]
    court_facet = facets_raw.get("_filter_court", {}).get("court", {}).get("buckets", [])
    facets["courts"] = [{"key": f["key"], "count": f["doc_count"]} for f in court_facet]

    return {
        "count": total_count,
        "results": results,
        "facets": facets,
        "query_corrected": query_corrected,
        "original_query": query,
        "corrected_query": search_query,
        "suggestions": suggestions,
    }


async def search_cases(query: Optional[str], filters: Optional[Dict] = None) -> List[Dict]:
    """Backward-compatible case search."""
    if not query:
        return []
    data = await search_kenyalaw(query=query, doc_type="judgment", limit=20)
    return data.get("results", [])


async def search_all(query: Optional[str], filters: Optional[Dict] = None) -> Dict[str, Any]:
    """Universal search across all content types."""
    if not query:
        return {"count": 0, "results": [], "facets": {}}

    doc_type = filters.get("doc_type") if filters else None
    court = filters.get("court") if filters else None
    page = filters.get("page", 1) if filters else 1
    ordering = filters.get("ordering", "-score") if filters else "-score"
    limit = filters.get("limit", 50) if filters else 50

    return await search_kenyalaw(
        query=query,
        doc_type=doc_type,
        court=court,
        page=page,
        ordering=ordering,
        limit=limit,
    )


async def fetch_document_text(url: str) -> str:
    """Try to fetch document text from kenyalaw.org. Returns whatever we can get."""
    try:
        resp = await _get(url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")

        # Try multiple selectors for content
        for selector in [
            ".document-content", ".judgment-body", ".legislation-body",
            "article", ".body", "#content", ".main-content",
            ".akn-block", "[data-body]", "main",
        ]:
            body = soup.select_one(selector)
            if body:
                text = body.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text[:8000]

        # Fallback: get all text
        text = soup.get_text(separator="\n", strip=True)
        return text[:8000] if len(text) > 100 else ""
    except Exception as e:
        logger.warning(f"Failed to fetch document text from {url}: {e}")
        return ""


async def scrape_statute(act_id: str) -> Dict[str, Any]:
    try:
        url = f"{KENYALAW_BASE}/legislation/{act_id}"
        resp = await _get(url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one("h1, .title, title")
        title = title_el.get_text(strip=True) if title_el else act_id
        body = soup.select_one(".body, #content, article, .document-content")
        full_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
        return {"act_id": act_id, "title": title, "full_text": full_text}
    except Exception as e:
        logger.warning(f"Failed to scrape statute {act_id}: {e}")
        return {"act_id": act_id, "title": act_id, "full_text": "Statute text unavailable. Visit kenyalaw.org to view this statute."}


async def scrape_constitution() -> Dict[str, Any]:
    try:
        url = f"{KENYALAW_BASE}/akn/ke/act/2010/constitution"
        resp = await _get(url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one("h1, .title, title")
        title = title_el.get_text(strip=True) if title_el else "Constitution of Kenya 2010"
        body = soup.select_one(".body, #content, article, .document-content")
        full_text = body.get_text(separator="\n\n", strip=True) if body else soup.get_text(separator="\n\n", strip=True)
        if len(full_text) > 100:
            return {"title": title, "full_text": full_text}
    except Exception as e:
        logger.warning(f"Failed to scrape constitution: {e}")

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

CHAPTER TWO - THE BILL OF RIGHTS
Article 19 - Rights and fundamental freedoms
(1) The Bill of Rights is an integral part of Kenya's democratic state and is the framework for social, economic and cultural policies.

Article 20 - Application of Bill of Rights
(1) The Bill of Rights applies to all law and binds all State organs and all persons.

CHAPTER SIX - THE LEGISLATURE
Article 93 - Functions of Parliament
(1) The legislative authority of the Republic is vested in and exercised by Parliament.

CHAPTER EIGHT - THE JUDICIARY
Article 159 - Judicial authority
(1) Judicial authority is derived from the people of Kenya and vests in, and is exercised by, the courts and tribunals."""


DEMO_CASES = [
    {
        "title": "Republic v Paul Kipkoech Korir & Another",
        "citation": "[2021] eKLR",
        "court": "High Court",
        "year": 2021,
        "subject_tags": ["Criminal Law", "Murder"],
        "full_text": "This is a criminal case involving charges of murder. The accused persons were charged with the murder of the deceased on or about 15th March 2019 in Nakuru County. The prosecution called 12 witnesses and tendered documentary evidence. The court examined the evidence of identification, the post-mortem report, and the ballistic analysis. The key issue was whether the prosecution had proved its case beyond reasonable doubt. The court considered the principles established in Republic v Okenye [2018] eKLR regarding circumstantial evidence and the requirements for conviction in murder cases under Section 203 of the Penal Code.",
        "judges": ["Justice J. M. Ngugi"],
    },
    {
        "title": "Anarita Karimi Njeru v Republic",
        "citation": "[1979] eKLR",
        "court": "High Court",
        "year": 1979,
        "subject_tags": ["Constitutional Law", "Human Rights", "Criminal Procedure"],
        "full_text": "This landmark case addressed the fundamental rights of accused persons under the Constitution of Kenya. The petitioner challenged the constitutionality of certain provisions of the Criminal Procedure Code that allowed detention without trial. The court held that the Bill of Rights under Chapter V of the then Constitution (now Chapter 4 of the 2010 Constitution) guaranteed the right to liberty and security of person. The court established the principle that any restriction on fundamental rights must be prescribed by law and be reasonably justifiable in a democratic society. This case remains a cornerstone of Kenyan constitutional jurisprudence and has been cited extensively in subsequent human rights litigation.",
        "judges": ["Justice H. R. Kneller", "Justice Chanan Singh"],
    },
    {
        "title": "Communications Commission of Kenya v Royal Media Services Limited & Others",
        "citation": "[2014] eKLR",
        "court": "Supreme Court",
        "year": 2014,
        "subject_tags": ["Constitutional Law", "Media Law", "Freedom of Expression"],
        "full_text": "This Supreme Court case addressed the balance between freedom of expression and the right of the state to regulate communications. The appellant, the Communications Commission of Kenya, challenged the Court of Appeal's decision that had struck down certain regulatory provisions. The Supreme Court examined Articles 33 and 34 of the Constitution of Kenya 2010 on freedom of expression and media freedom respectively. The court held that while freedom of expression is a fundamental right, it is not absolute and may be limited in accordance with Article 24 of the Constitution. The court established important principles on the doctrine of fair comment in media law and the role of the state in regulating broadcasting frequencies.",
        "judges": ["Chief Justice Dr. Willy Mutunga", "Justice Jackton Ojwang", "Justice Njoki Ndung'u"],
    },
    {
        "title": "Republic v Mwangi v Attorney General",
        "citation": "[2019] eKLR",
        "court": "High Court",
        "year": 2019,
        "subject_tags": ["Employment Law", "Labour Relations", "Constitutional Law"],
        "full_text": "This case concerned the rights of public servants to fair labour practices under Article 41 of the Constitution of Kenya 2010. The petitioner, a senior government officer, challenged his dismissal from the civil service on grounds of procedural unfairness. The court examined the Employment Act 2007 and the Public Service (Values and Principles) Act 2015. The court held that public servants are entitled to the same employment protections as private sector employees and that the state must follow fair administrative action principles under Article 47 of the Constitution when terminating employment. The court awarded damages for wrongful dismissal and ordered reinstatement.",
        "judges": ["Justice Radido Stephen"],
    },
    {
        "title": "Kenya Revenue Authority v Yaya Towers Limited",
        "citation": "[2020] eKLR",
        "court": "Court of Appeal",
        "year": 2020,
        "subject_tags": ["Tax Law", "Revenue", "Commercial Law"],
        "full_text": "This Court of Appeal case addressed the interpretation of the Income Tax Act and the obligations of taxpayers in Kenya. The appellant, Kenya Revenue Authority, appealed against the High Court's decision that had ruled in favour of the respondent, Yaya Towers Limited, on the question of capital gains tax on the disposal of property. The court examined the definition of 'capital gains' under the Eighth Schedule to the Income Tax Act and the meaning of 'disposal' in the context of corporate restructuring. The court held that the transfer of shares in a company that owns immovable property constitutes a disposal of property for capital gains tax purposes. The court also addressed the limitation period for tax assessments under Section 31 of the Tax Procedures Act.",
        "judges": ["Justice Asike Makhandia", "Justice Patrick Kiage"],
    },
]
