import os
import httpx
import asyncio
import logging
import re
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
    "causelist": "Cause List",
    "journal": "Journal",
}


async def _get(url: str, params: Optional[Dict] = None) -> httpx.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Juriscore/1.0 (student research bot)",
        "Accept": "application/json",
    }
    for attempt in range(2):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Scrape attempt {attempt+1} failed for {url}: {e}")
                await asyncio.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after retries")


def _build_result(item: Dict) -> Dict[str, Any]:
    doc_type = item.get("doc_type", "unknown")
    frbr_uri = item.get("expression_frbr_uri", "")
    url = f"{KENYALAW_BASE}{frbr_uri}" if frbr_uri else ""

    # Extract case number from title or case_number field
    case_numbers = item.get("case_number", [])
    case_number = case_numbers[0] if case_numbers else ""

    # Get highlights as excerpt
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
    }


async def search_kenyalaw(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    ordering: str = "-score",
    limit: int = 20,
) -> Dict[str, Any]:
    params = {
        "search": query,
        "page": str(page),
        "ordering": ordering,
    }

    # Doc type filter (e.g., "judgment", "legislation", "gazette", etc.)
    if doc_type and doc_type != "all":
        params["_filter_doc_type"] = doc_type

    # Court filter
    if court and court != "all":
        params["_filter_court"] = court

    # Date range
    if date_from and date_to:
        params["date__range"] = f"{date_from}__{date_to}"
    elif date_from:
        params["date__gte"] = date_from
    elif date_to:
        params["date__lte"] = date_to

    try:
        resp = await _get(KENYALAW_SEARCH_API, params=params)
        data = resp.json()
    except Exception as e:
        logger.error(f"kenyalaw.org search failed: {e}")
        return {"count": 0, "results": [], "facets": {}}

    results = []
    for item in data.get("results", [])[:limit]:
        results.append(_build_result(item))

    # Extract facets
    facets_raw = data.get("facets", {})
    facets = {}

    doc_type_facet = facets_raw.get("_filter_doc_type", {}).get("doc_type", {}).get("buckets", [])
    facets["doc_types"] = [{"key": f["key"], "count": f["doc_count"]} for f in doc_type_facet]

    court_facet = facets_raw.get("_filter_court", {}).get("court", {}).get("buckets", [])
    facets["courts"] = [{"key": f["key"], "count": f["doc_count"]} for f in court_facet]

    year_facet = facets_raw.get("_filter_year", {}).get("year", {}).get("buckets", [])
    facets["years"] = [{"key": f["key"], "count": f["doc_count"]} for f in year_facet]

    return {
        "count": data.get("count", 0),
        "results": results,
        "facets": facets,
    }


async def get_kenyalaw_document(doc_id: str) -> Optional[Dict]:
    try:
        resp = await _get(f"{KENYALAW_BASE}/api/documents/{doc_id}/")
        return resp.json()
    except Exception as e:
        logger.warning(f"Failed to fetch document {doc_id}: {e}")
        return None


async def search_cases(query: Optional[str], filters: Optional[Dict] = None) -> List[Dict]:
    """Backward-compatible case search. Returns only judgment-type results."""
    if not query:
        return []
    data = await search_kenyalaw(
        query=query,
        doc_type="judgment",
        court=filters.get("court") if filters else None,
        limit=20,
    )
    return data.get("results", [])


async def search_all(query: Optional[str], filters: Optional[Dict] = None) -> Dict[str, Any]:
    """Universal search across all content types on kenyalaw.org."""
    if not query:
        return {"count": 0, "results": [], "facets": {}}

    doc_type = filters.get("doc_type") if filters else None
    court = filters.get("court") if filters else None
    date_from = filters.get("date_from") if filters else None
    date_to = filters.get("date_to") if filters else None
    page = filters.get("page", 1) if filters else 1
    ordering = filters.get("ordering", "-score") if filters else "-score"
    limit = filters.get("limit", 20) if filters else 20

    return await search_kenyalaw(
        query=query,
        doc_type=doc_type,
        court=court,
        date_from=date_from,
        date_to=date_to,
        page=page,
        ordering=ordering,
        limit=limit,
    )


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

CHAPTER SIX - THE LEGISLATURE
Article 93 - Functions of Parliament
(1) The legislative authority of the Republic is vested in and exercised by Parliament.
(2) Parliament enacts legislation as provided for in this Constitution.

CHAPTER EIGHT - THE JUDICIARY
Article 159 - Judicial authority
(1) Judicial authority is derived from the people of Kenya and vests in, and is exercised by, the courts and tribunals.

Article 160 - Independence of the Judiciary
(1) In the exercise of judicial authority, the Judiciary, as constituted by Article 161, shall be subject only to this Constitution and the law and shall not be subject to the control or direction of any person or authority."""
