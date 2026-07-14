import httpx
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

AFRICALII_BASE = "https://africanlii.org"
AFRICALII_SEARCH = f"{AFRICALII_BASE}/ajax/search"
SEMAPHORE = asyncio.Semaphore(3)

# African regional courts and tribunals
AFRICAN_COURTS = [
    "African Court on Human and Peoples' Rights",
    "ECOWAS Court of Justice",
    "East African Court of Justice",
    "SADC Tribunal",
    "African Commission on Human and Peoples' Rights",
    "African Committee of Experts on the Rights and Welfare of the Child",
    "International Criminal Court",
    "International Court of Justice",
    "African Union Assembly",
    "African Union Executive Council",
]

# African countries with legal databases
AFRICAN_JURISDICTIONS = {
    "kenya": {"name": "Kenya", "lii": "kenyalaw.org", "court": "High Court"},
    "nigeria": {"name": "Nigeria", "lii": "nigerianlii.org", "court": "Federal High Court"},
    "south_africa": {"name": "South Africa", "lii": "saflii.org", "court": "Constitutional Court"},
    "ghana": {"name": "Ghana", "lii": "ghanali.org", "court": "High Court"},
    "tanzania": {"name": "Tanzania", "lii": "tzlii.org", "court": "High Court"},
    "uganda": {"name": "Uganda", "lii": "uglii.org", "court": "High Court"},
    "rwanda": {"name": "Rwanda", "lii": "rwandalii.org", "court": "High Court"},
    "ethiopia": {"name": "Ethiopia", "lii": "ethiopianlii.org", "court": "Federal High Court"},
    "egypt": {"name": "Egypt", "lii": "egyptianlii.org", "court": "Supreme Court"},
    "morocco": {"name": "Morocco", "lii": "moroccolii.org", "court": "Supreme Court"},
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


def _build_african_result(item: Dict, source: str = "AfricanLII") -> Dict[str, Any]:
    """Build a standardized result from African legal sources."""
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
        "jurisdiction": "africa",
    }


async def search_africanlii(
    query: str,
    doc_type: Optional[str] = None,
    country: Optional[str] = None,
    page: int = 1,
    limit: int = 30,
) -> Dict[str, Any]:
    """Search African Legal Information Institute."""
    results = []

    try:
        # Try the AfricanLII search API
        params = {
            "search": query,
            "page": str(page),
        }
        if doc_type:
            params["type"] = doc_type
        if country:
            params["country"] = country

        resp = await _get(f"{AFRICALII_BASE}/search", params=params)
        soup = BeautifulSoup(resp.text, "lxml")

        # Parse search results
        result_items = soup.select(".result-item, .search-result, article, .document")
        for item in result_items[:limit]:
            title_el = item.select_one("h3, h4, .title, a")
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.select_one("a[href]")
            url = f"{AFRICALII_BASE}{link_el['href']}" if link_el else ""
            excerpt_el = item.select_one("p, .excerpt, .summary")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""
            court_el = item.select_one(".court, .jurisdiction")
            court = court_el.get_text(strip=True) if court_el else ""

            if title:
                results.append(_build_african_result({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt[:300],
                    "court": court,
                    "doc_type": "judgment",
                    "doc_type_label": "Case Law",
                }, "AfricanLII"))

    except Exception as e:
        logger.warning(f"AfricanLII search failed: {e}")

    # Also search individual country LIIs
    if country and country.lower() in AFRICAN_JURISDICTIONS:
        country_info = AFRICAN_JURISDICTIONS[country.lower()]
        try:
            country_results = await _search_country_lii(query, country_info, limit)
            results.extend(country_results)
        except Exception as e:
            logger.warning(f"Country LII search failed for {country}: {e}")

    return {
        "count": len(results),
        "results": results[:limit],
        "facets": {"doc_types": [], "courts": []},
        "source": "AfricanLII",
        "jurisdiction": "africa",
    }


async def _search_country_lii(query: str, country_info: Dict, limit: int) -> List[Dict]:
    """Search a specific country's Legal Information Institute."""
    results = []
    base_url = f"https://{country_info['lii']}"

    try:
        params = {"search": query}
        resp = await _get(f"{base_url}/search", params=params)
        soup = BeautifulSoup(resp.text, "lxml")

        result_items = soup.select(".result-item, .search-result, article, .document")
        for item in result_items[:limit]:
            title_el = item.select_one("h3, h4, .title, a")
            title = title_el.get_text(strip=True) if title_el else ""
            link_el = item.select_one("a[href]")
            url = f"{base_url}{link_el['href']}" if link_el else ""
            excerpt_el = item.select_one("p, .excerpt")
            excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""

            if title:
                results.append(_build_african_result({
                    "title": title,
                    "url": url,
                    "excerpt": excerpt[:300],
                    "court": country_info["court"],
                    "doc_type": "judgment",
                    "doc_type_label": "Case Law",
                }, f"{country_info['name']} LII"))

    except Exception as e:
        logger.warning(f"Country LII search failed: {e}")

    return results


async def search_african_court(
    query: str,
    court: Optional[str] = None,
    limit: int = 30,
) -> Dict[str, Any]:
    """Search African regional courts (ECOWAS, EACJ, SADC, etc.)."""
    results = []

    court_urls = {
        "ECOWAS Court": "https://ecowascourt.org/search",
        "East African Court of Justice": "https://www.eacj.org/search",
        "African Court": "https://african court.org/search",
        "SADC Tribunal": "https://sadctribunal.org/search",
    }

    search_urls = court_urls.values()
    if court and court in court_urls:
        search_urls = [court_urls[court]]

    for base_url in search_urls:
        try:
            params = {"search": query}
            resp = await _get(base_url, params=params)
            soup = BeautifulSoup(resp.text, "lxml")

            result_items = soup.select(".result-item, .search-result, article, .document, .case")
            for item in result_items[:limit]:
                title_el = item.select_one("h3, h4, .title, a")
                title = title_el.get_text(strip=True) if title_el else ""
                link_el = item.select_one("a[href]")
                url = f"{base_url}{link_el['href']}" if link_el else ""
                excerpt_el = item.select_one("p, .excerpt, .summary")
                excerpt = excerpt_el.get_text(strip=True) if excerpt_el else ""

                if title:
                    results.append(_build_african_result({
                        "title": title,
                        "url": url,
                        "excerpt": excerpt[:300],
                        "court": court or "African Regional Court",
                        "doc_type": "judgment",
                        "doc_type_label": "Case Law",
                    }, "African Court"))

        except Exception as e:
            logger.warning(f"African court search failed for {base_url}: {e}")

    return {
        "count": len(results),
        "results": results[:limit],
        "facets": {"doc_types": [], "courts": []},
        "source": "African Courts",
        "jurisdiction": "africa",
    }


def get_african_jurisdictions() -> List[Dict]:
    """Return list of available African jurisdictions."""
    return [
        {"id": k, "name": v["name"], "lii": v["lii"], "court": v["court"]}
        for k, v in AFRICAN_JURISDICTIONS.items()
    ]


def get_african_courts() -> List[str]:
    """Return list of African regional courts."""
    return AFRICAN_COURTS
