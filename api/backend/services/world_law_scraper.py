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
    "klimmit": {
        "name": "Kenya Law",
        "base": "https://kenyalaw.org",
        "search": "https://kenyalaw.org/search/api/documents/",
        "types": ["judgment", "legislation"],
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

    # Search WorldLII
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

    # Search specific jurisdiction if provided
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

    # Search by specific source if provided
    if source and source in WORLD_SOURCES:
        source_info = WORLD_SOURCES[source]
        try:
            source_results = await _search_source(query, source_info, limit)
            results.extend(source_results)
        except Exception as e:
            logger.warning(f"Source search failed for {source}: {e}")

    return {
        "count": len(results),
        "results": results[:limit],
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

    # Search across multiple sources in parallel
    search_tasks = []
    for source_key, source_info in WORLD_SOURCES.items():
        search_tasks.append(_search_source(query, source_info, limit))

    if search_tasks:
        task_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for result in task_results:
            if isinstance(result, list):
                results.extend(result)

    # Filter by legal system if specified
    if legal_system:
        system_info = next((s for s in LEGAL_SYSTEMS if s["id"] == legal_system), None)
        if system_info:
            # This is a simplified filter - in production you'd want to tag results with their legal system
            pass

    # Filter by country if specified
    if country:
        results = [r for r in results if country.lower() in r.get("court", "").lower() or country.lower() in r.get("title", "").lower()]

    return {
        "count": len(results),
        "results": results[:limit],
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
