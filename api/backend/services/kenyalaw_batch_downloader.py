"""
KenyaLaw.org Batch Downloader
Progressively downloads the entire KenyaLaw.org website for local access.
Runs as a background service with rate limiting and incremental sync.
"""
import asyncio
import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from pathlib import Path
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

# KenyaLaw.org base URLs
KENYALAW_BASE = "https://www.kenyalaw.org"
KENYALAW_SEARCH_API = "https://www.kenyalaw.org/search"
KENYALAW_CASES_URL = f"{KENYALAW_BASE}/kl/"
KENYALAW_LEGISLATION_URL = f"{KENYALAW_BASE}/kl/legislation/"

# Rate limiting: 1 request per second to be respectful
RATE_LIMIT_DELAY = 1.0
MAX_CONCURRENT = 3
BATCH_SIZE = 50

# Document types to download
DOC_TYPES = [
    "judgment", "ruling", "decision", "case",
    "legislation", "act", "statute", "regulation",
    "article", "law_report", "legal_news",
]

# Kenyan courts
KENYAN_COURTS = [
    "Supreme Court", "Court of Appeal", "High Court",
    "Environment and Land Court", "Employment and Labour Relations Court",
    "Magistrate Court", "Kadhi Court", "Military Court",
]

# Search queries to systematically download all content
SYSTEMATIC_QUERIES = [
    # Constitutional Law
    "constitutional law", "constitution", "fundamental rights",
    "judicial review", "amendment", "sovereignty",
    # Criminal Law
    "criminal law", "murder", "manslaughter", "theft", "robbery",
    "fraud", "corruption", "drug trafficking", "sexual offences",
    # Civil Law
    "contract law", "tort", "negligence", "damages",
    "employment law", "labor law", "dismissal",
    # Family Law
    "family law", "marriage", "divorce", "custody", "inheritance",
    "succession", "matrimonial",
    # Land Law
    "land law", "property law", "lease", "mortgage",
    "eviction", "boundary", "compulsory acquisition",
    # Commercial Law
    "company law", "insolvency", "bankruptcy", "intellectual property",
    "banking law", "insurance law", "tax law",
    # Environmental Law
    "environmental law", "climate change", "pollution",
    "conservation", "natural resources",
    # International Law
    "international law", "treaty", "extradition",
    "human rights", "refugee law",
    # Procedural Law
    "civil procedure", "criminal procedure", "evidence law",
    "limitation period", "jurisdiction",
    # Case law by court
    "Supreme Court", "Court of Appeal", "High Court",
    # Recent years
    "2024", "2023", "2022", "2021", "2020",
    # Major cases
    "Marbury v Madison", "Republic v Elburgon", "Njoya v Attorney General",
    "Mumo Matemu", "Anarita Karimi Njeru",
    # Legal concepts
    "precedent", "stare decisis", "ratio decidendi",
    "obiter dictum", "dissenting opinion",
    # Specific areas
    "military law", "election law", "media law",
    "health law", "education law", "housing law",
    # Counties
    "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret",
    "Thika", "Malindi", "Kitale", "Garissa", "Kakamega",
]


class KenyaLawBatchDownloader:
    """Downloads KenyaLaw.org content in batches with rate limiting."""

    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.downloaded_ids: Set[str] = set()
        self.stats = {
            "total_downloaded": 0,
            "cases": 0,
            "legislation": 0,
            "articles": 0,
            "errors": 0,
            "skipped": 0,
        }
        self.running = False
        self.progress_callback = None

    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "JurisCache/1.0 (Legal Research Tool)",
                "Accept": "text/html,application/json",
            }
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        await asyncio.sleep(RATE_LIMIT_DELAY)

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting and error handling."""
        if not self.session:
            return None

        try:
            await self._rate_limit()
            response = await self.session.get(url)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} for {url}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            self.stats["errors"] += 1
            return None

    async def _fetch_json(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Fetch JSON API endpoint with rate limiting."""
        if not self.session:
            return None

        try:
            await self._rate_limit()
            response = await self.session.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"HTTP {response.status_code} for {url}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch JSON from {url}: {e}")
            self.stats["errors"] += 1
            return None

    def _extract_case_data(self, html: str, url: str) -> Optional[Dict]:
        """Extract case data from HTML page."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Extract title
            title_elem = soup.find("h1") or soup.find("title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            # Extract citation
            citation = ""
            citation_elem = soup.find("span", class_="citation") or soup.find("div", class_="citation")
            if citation_elem:
                citation = citation_elem.get_text(strip=True)

            # Extract court
            court = ""
            court_elem = soup.find("span", class_="court") or soup.find("div", class_="court")
            if court_elem:
                court = court_elem.get_text(strip=True)

            # Extract year
            year = 0
            year_elem = soup.find("span", class_="year") or soup.find("div", class_="year")
            if year_elem:
                try:
                    year = int(year_elem.get_text(strip=True)[:4])
                except (ValueError, IndexError):
                    pass

            # Extract full text
            full_text = ""
            content_elem = soup.find("div", class_="content") or soup.find("article")
            if content_elem:
                full_text = content_elem.get_text(separator="\n", strip=True)

            # Extract excerpt
            excerpt = full_text[:500] if full_text else ""

            if title:
                doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
                return {
                    "id": f"case_{doc_id}",
                    "title": title,
                    "citation": citation,
                    "court": court,
                    "year": year,
                    "doc_type": "judgment",
                    "excerpt": excerpt,
                    "url": url,
                    "full_text": full_text,
                    "score": 1.0,
                }
        except Exception as e:
            logger.warning(f"Failed to extract case data from {url}: {e}")

        return None

    def _extract_legislation_data(self, html: str, url: str) -> Optional[Dict]:
        """Extract legislation data from HTML page."""
        try:
            soup = BeautifulSoup(html, "lxml")

            title_elem = soup.find("h1") or soup.find("title")
            title = title_elem.get_text(strip=True) if title_elem else ""

            full_text = ""
            content_elem = soup.find("div", class_="content") or soup.find("article")
            if content_elem:
                full_text = content_elem.get_text(separator="\n", strip=True)

            excerpt = full_text[:500] if full_text else ""

            if title:
                doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
                return {
                    "id": f"leg_{doc_id}",
                    "title": title,
                    "citation": "",
                    "court": "",
                    "year": 0,
                    "doc_type": "legislation",
                    "excerpt": excerpt,
                    "url": url,
                    "full_text": full_text,
                    "score": 1.0,
                }
        except Exception as e:
            logger.warning(f"Failed to extract legislation data from {url}: {e}")

        return None

    async def _download_from_search(self, query: str, doc_type: str = None, limit: int = 50) -> List[Dict]:
        """Download documents from KenyaLaw search API."""
        results = []

        params = {"search": query, "page": "1"}
        if doc_type:
            params["type"] = doc_type

        data = await self._fetch_json(KENYALAW_SEARCH_API, params=params)
        if not data:
            return results

        items = data.get("results", [])
        for item in items[:limit]:
            doc_id = item.get("id", "")
            if doc_id and doc_id not in self.downloaded_ids:
                results.append(item)
                self.downloaded_ids.add(doc_id)

        return results

    async def _download_case_page(self, url: str) -> Optional[Dict]:
        """Download and parse a single case page."""
        html = await self._fetch_page(url)
        if html:
            return self._extract_case_data(html, url)
        return None

    async def _download_legislation_page(self, url: str) -> Optional[Dict]:
        """Download and parse a single legislation page."""
        html = await self._fetch_page(url)
        if html:
            return self._extract_legislation_data(html, url)
        return None

    async def download_batch(self, queries: List[str], doc_type: str = None) -> int:
        """Download a batch of documents for given queries."""
        from api.backend.services.kenyalaw_local_db import sync_live_results_to_db

        total_downloaded = 0

        for query in queries:
            try:
                items = await self._download_from_search(query, doc_type)

                if items:
                    await sync_live_results_to_db(items)
                    total_downloaded += len(items)

                    # Update stats
                    for item in items:
                        dtype = item.get("doc_type", "")
                        if dtype in ("judgment", "ruling", "decision", "case"):
                            self.stats["cases"] += 1
                        elif dtype in ("legislation", "act", "statute", "regulation"):
                            self.stats["legislation"] += 1
                        else:
                            self.stats["articles"] += 1

                    self.stats["total_downloaded"] += len(items)
                    logger.info(f"Downloaded {len(items)} items for query: {query}")

                if self.progress_callback:
                    self.progress_callback(self.stats)

            except Exception as e:
                logger.error(f"Failed to download batch for '{query}': {e}")
                self.stats["errors"] += 1

        return total_downloaded

    async def full_sync(self):
        """Perform a full sync of KenyaLaw.org content."""
        self.running = True
        logger.info("Starting full KenyaLaw.org sync...")

        try:
            # Split queries into batches
            for i in range(0, len(SYSTEMATIC_QUERIES), BATCH_SIZE):
                if not self.running:
                    break

                batch = SYSTEMATIC_QUERIES[i:i + BATCH_SIZE]
                await self.download_batch(batch)

                logger.info(f"Progress: {self.stats['total_downloaded']} documents downloaded")

            # Also download by court
            for court in KENYAN_COURTS:
                if not self.running:
                    break
                await self.download_batch([court], doc_type="judgment")

            # Download recent years
            for year in range(2024, 2015, -1):
                if not self.running:
                    break
                await self.download_batch([str(year)])

        finally:
            self.running = False
            logger.info(f"Full sync completed. Stats: {self.stats}")

    def stop(self):
        """Stop the download process."""
        self.running = False


# Singleton instance
_downloader: Optional[KenyaLawBatchDownloader] = None


async def get_downloader() -> KenyaLawBatchDownloader:
    """Get or create the batch downloader instance."""
    global _downloader
    if _downloader is None:
        _downloader = KenyaLawBatchDownloader()
    return _downloader


async def start_background_sync():
    """Start background sync in a separate task."""
    downloader = await get_downloader()

    if downloader.running:
        return {"status": "already_running", "stats": downloader.stats}

    async def _run_sync():
        async with downloader:
            await downloader.full_sync()

    asyncio.create_task(_run_sync())
    return {"status": "started", "stats": downloader.stats}


async def stop_background_sync():
    """Stop background sync."""
    downloader = await get_downloader()
    downloader.stop()
    return {"status": "stopping", "stats": downloader.stats}


async def get_sync_progress():
    """Get current sync progress."""
    downloader = await get_downloader()
    return {
        "running": downloader.running,
        "stats": downloader.stats,
    }
