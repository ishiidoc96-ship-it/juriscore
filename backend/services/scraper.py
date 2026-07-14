import os
import httpx
import asyncio
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

BASE_URL = os.getenv("KENYALAW_BASE", "https://www.kenyalaw.org")
SEMAPHORE = asyncio.Semaphore(1)


async def _get(url: str, params: Optional[Dict] = None) -> httpx.Response:
    headers = {"User-Agent": "Juriscore/1.0 (student research bot)"}
    for attempt in range(3):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers, params=params)
                    resp.raise_for_status()
                    return resp
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Scrape attempt {attempt+1} failed: {e}")
                await asyncio.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url} after retries")


async def scrape_case(url: str) -> Dict[str, Any]:
    resp = await _get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.select_one("h1, .case-title, title")
    title = title.get_text(strip=True) if title else ""
    citation = ""
    citation_tag = soup.select_one(".citation")
    citation = citation_tag.get_text(strip=True) if citation_tag else ""
    court = ""
    court_tag = soup.select_one(".court")
    court = court_tag.get_text(strip=True) if court_tag else ""
    year = 0
    import re
    m = re.search(r"(19|20)\d{2}", citation or title or "")
    if m:
        year = int(m.group(0))
    judges: List[str] = []
    judges_tag = soup.select_one(".judges")
    if judges_tag:
        judges = [j.strip() for j in judges_tag.get_text(separator=",").split(",") if j.strip()]
    body = soup.select_one(".body, .case-body, #content, article")
    full_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
    links: List[str] = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "/case/" in href or "/judgment/" in href:
            links.append(urljoin(BASE_URL, href))
    return {
        "title": title,
        "citation": citation,
        "court": court,
        "year": year,
        "judges": judges,
        "full_text": full_text,
        "cases_cited": links,
        "subject_tags": [],
    }


async def search_cases(query: Optional[str], filters: Optional[Dict] = None) -> List[Dict]:
    params = {"q": query or "", "format": "json"}
    if filters:
        params.update({k: v for k, v in filters.items() if v is not None})
    resp = await _get(urljoin(BASE_URL, "/search"), params=params)
    try:
        return resp.json()
    except Exception:
        soup = BeautifulSoup(resp.text, "lxml")
        results: List[Dict] = []
        for item in soup.select(".result-item"):
            a = item.select_one("a[href]")
            href = urljoin(BASE_URL, a.get("href", "")) if a else ""
            title = a.get_text(strip=True) if a else ""
            results.append({"title": title, "url": href})
        return results


async def scrape_statute(act_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/lex/actview.xql?actid={quote_plus(act_id)}"
    resp = await _get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.select_one("h1, .title, title")
    title = title.get_text(strip=True) if title else act_id
    body = soup.select_one(".body, #content, article")
    full_text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
    return {"act_id": act_id, "title": title, "full_text": full_text}


async def scrape_constitution() -> Dict[str, Any]:
    url = f"{BASE_URL}/lex/actview.xql?actid=Const2010"
    resp = await _get(url)
    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.select_one("h1, .title, title")
    title = title.get_text(strip=True) if title else "Constitution of Kenya 2010"
    body = soup.select_one(".body, #content, article")
    full_text = body.get_text(separator="\n\n", strip=True) if body else soup.get_text(separator="\n\n", strip=True)
    return {"title": title, "full_text": full_text}
