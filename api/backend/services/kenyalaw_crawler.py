"""
KenyaLaw.org Full Site Crawler
Discovers and downloads every document from KenyaLaw.org.
Follows listing pages, discovers document URLs, downloads full text.
Runs as a background service with rate limiting and resume support.
"""
import asyncio
import logging
import hashlib
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set, Tuple
from pathlib import Path
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

KENYALAW_BASE = "https://www.kenyalaw.org"

# Rate limiting: 5 seconds per robots.txt Crawl-delay
RATE_LIMIT_DELAY = 5.0
MAX_CONCURRENT = 2

# Kenyan courts with their listing page codes
KENYAN_COURTS = [
    "KEHC",    # High Court
    "KECA",    # Court of Appeal
    "KESC",    # Supreme Court
    "KEELC",   # Environment and Land Court
    "KEELRC",  # Employment and Labour Relations Court
    "KEMC",    # Magistrate Court
    "KEKC",    # Kadhi Court
    "KEIC",    # Industrial Court (legacy)
    "SCC",     # Small Claims Court
]

# Years to crawl (KenyaLaw has data from ~2000 onwards, heavy from 2015)
YEARS = list(range(2026, 2014, -1))

# Max listing pages per court/year (site limits to 10)
MAX_LISTING_PAGES = 10

# Listings to crawl: (url_pattern, doc_type, description)
LISTINGS = [
    # Judgments by court
    *[(f"/judgments/{court}/", "judgment", f"Judgments - {court}") for court in KENYAN_COURTS],
    # Judgments by court and year
    *[(f"/judgments/{court}/{year}/", "judgment", f"Judgments - {court} {year}")
      for court in KENYAN_COURTS for year in YEARS],
    # Legislation
    ("/legislation/", "legislation", "Legislation (all)"),
    ("/legislation/recent", "legislation", "Legislation (recent)"),
    ("/legislation/counties", "legislation", "Legislation (counties)"),
    # Articles
    ("/articles/", "article", "Articles"),
    # Bills
    ("/bills/", "bill", "Bills"),
    # Cause lists
    ("/causelists/", "cause_list", "Cause Lists"),
    # Gazettes
    ("/gazettes/", "gazette", "Gazettes"),
    # Taxonomy pages
    ("/taxonomy/collections", "article", "Collections"),
    ("/taxonomy/collections/collections-treaties", "treaty", "Treaties"),
    ("/taxonomy/elections", "article", "Elections"),
    ("/taxonomy/publications", "article", "Publications"),
    ("/taxonomy/foreign-legislation/foreign-legislation-east-african-community-eac",
     "legislation", "EAC Legislation"),
]

# Browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class KenyaLawCrawler:
    """Full site crawler that discovers and downloads every document."""

    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.downloaded_urls: Set[str] = set()
        self.discovered_urls: Set[str] = set()
        self.stats = {
            "total_discovered": 0,
            "total_downloaded": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "judgments": 0,
            "legislation": 0,
            "articles": 0,
            "bills": 0,
            "other": 0,
            "current_listing": "",
            "listings_done": 0,
            "listings_total": 0,
        }
        self.running = False
        self.progress_callback = None

    async def __aenter__(self):
        self.session = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=HEADERS,
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()

    async def _rate_limit(self):
        await asyncio.sleep(RATE_LIMIT_DELAY)

    async def _fetch(self, url: str) -> Optional[str]:
        """Fetch a page with rate limiting."""
        if not self.session:
            return None
        full_url = url if url.startswith("http") else f"{KENYALAW_BASE}{url}"
        try:
            await self._rate_limit()
            response = await self.session.get(full_url)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} for {full_url}")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch {full_url}: {e}")
            self.stats["total_errors"] += 1
            return None

    def _extract_links_from_listing(self, html: str, base_url: str) -> List[str]:
        """Extract document links from a listing page."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            # Match AKN document URLs (judgments, acts, articles, etc.)
            if "/akn/" in href:
                full = urljoin(KENYALAW_BASE, href)
                # Remove trailing spaces and fragments
                full = full.split("#")[0].strip()
                if full not in self.discovered_urls:
                    links.append(full)
        return links

    def _get_max_page(self, html: str) -> int:
        """Find the maximum page number from pagination links."""
        soup = BeautifulSoup(html, "lxml")
        max_page = 1
        for a in soup.find_all("a", href=True):
            m = re.search(r"page=(\d+)", a["href"])
            if m:
                pg = int(m.group(1))
                if pg > max_page:
                    max_page = pg
        return min(max_page, MAX_LISTING_PAGES)

    async def _crawl_listing(self, listing_path: str, doc_type: str) -> List[str]:
        """Crawl a listing page and all its pagination pages. Returns discovered URLs."""
        all_urls = []

        # Fetch page 1
        html = await self._fetch(listing_path)
        if not html:
            return all_urls

        # Extract links from page 1
        urls = self._extract_links_from_listing(html, listing_path)
        all_urls.extend(urls)
        self.discovered_urls.update(urls)

        # Find max page
        max_page = self._get_max_page(html)
        logger.info(f"Listing {listing_path}: {len(urls)} docs on page 1, max_page={max_page}")

        # Crawl remaining pages
        for pg in range(2, max_page + 1):
            if not self.running:
                break
            separator = "&" if "?" in listing_path else "?"
            page_url = f"{listing_path}{separator}page={pg}"
            html = await self._fetch(page_url)
            if html:
                urls = self._extract_links_from_listing(html, listing_path)
                all_urls.extend(urls)
                self.discovered_urls.update(urls)
                logger.info(f"  Page {pg}: {len(urls)} docs")

        return all_urls

    def _extract_document_data(self, html: str, url: str) -> Optional[Dict]:
        """Extract full text and metadata from a document page."""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Title
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                # Remove " - Kenya Law" suffix
                title = re.sub(r"\s*[-–]\s*Kenya\s*Law\s*$", "", title, flags=re.I)

            # Full text from the main content area
            full_text = ""
            content = (soup.find("div", id="doc-content") or
                      soup.find("article") or
                      soup.find("div", class_="content") or
                      soup.find("main"))
            if content:
                full_text = content.get_text(separator="\n", strip=True)

            if not full_text:
                # Fallback: get all text
                full_text = soup.get_text(separator="\n", strip=True)

            if not title and not full_text:
                return None

            # Extract doc_type from URL
            doc_type = "judgment"
            if "/act/" in url or "/legislation/" in url:
                doc_type = "legislation"
            elif "/article" in url:
                doc_type = "article"
            elif "/bill/" in url:
                doc_type = "bill"
            elif "/judgment/" in url:
                doc_type = "judgment"

            # Extract court from URL
            court = ""
            court_match = re.search(r"/judgment/(ke\w+)/", url, re.I)
            if court_match:
                court = court_match.group(1).upper()

            # Extract year from URL
            year = 0
            year_match = re.search(r"/(\d{4})/", url)
            if year_match:
                year = int(year_match.group(1))

            # Build ID from URL
            doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]

            # Excerpt
            excerpt = full_text[:500] if full_text else ""

            return {
                "id": f"kl_{doc_id}",
                "title": title,
                "citation": "",
                "court": court,
                "year": year,
                "doc_type": doc_type,
                "excerpt": excerpt,
                "url": url,
                "full_text": full_text,
                "score": 1.0,
            }
        except Exception as e:
            logger.warning(f"Failed to extract data from {url}: {e}")
            self.stats["total_errors"] += 1
            return None

    async def _download_document(self, url: str) -> Optional[Dict]:
        """Download and parse a single document."""
        html = await self._fetch(url)
        if html:
            return self._extract_document_data(html, url)
        return None

    async def _save_batch(self, documents: List[Dict]):
        """Save a batch of documents to the local database."""
        if not documents:
            return
        from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
        await sync_live_results_to_db(documents)

    def _update_stats(self, doc_type: str, count: int = 1):
        """Update statistics by document type."""
        if doc_type in ("judgment", "ruling", "decision"):
            self.stats["judgments"] += count
        elif doc_type in ("legislation", "act", "statute", "regulation"):
            self.stats["legislation"] += count
        elif doc_type in ("article", "law_report"):
            self.stats["articles"] += count
        elif doc_type == "bill":
            self.stats["bills"] += count
        else:
            self.stats["other"] += count
        self.stats["total_downloaded"] += count

    async def full_crawl(self):
        """Crawl the entire KenyaLaw.org site."""
        self.running = True
        self.stats["listings_total"] = len(LISTINGS)
        logger.info(f"Starting full KenyaLaw.org crawl ({len(LISTINGS)} listings to process)...")

        try:
            # Phase 1: Discover all document URLs from listing pages
            logger.info("Phase 1: Discovering document URLs from listing pages...")
            for listing_path, doc_type, description in LISTINGS:
                if not self.running:
                    break

                self.stats["current_listing"] = description
                logger.info(f"Crawling listing: {description} ({listing_path})")

                urls = await self._crawl_listing(listing_path, doc_type)
                self.stats["total_discovered"] = len(self.discovered_urls)
                self.stats["listings_done"] += 1

                if self.progress_callback:
                    self.progress_callback(self.stats)

                logger.info(f"  Discovered {len(urls)} URLs (total: {len(self.discovered_urls)})")

            logger.info(f"Phase 1 complete: {len(self.discovered_urls)} documents discovered")

            # Phase 2: Download each document
            logger.info("Phase 2: Downloading documents...")
            batch = []
            batch_size = 20  # Save to DB every 20 docs

            for url in self.discovered_urls:
                if not self.running:
                    break

                if url in self.downloaded_urls:
                    self.stats["total_skipped"] += 1
                    continue

                doc = await self._download_document(url)
                if doc:
                    batch.append(doc)
                    self.downloaded_urls.add(url)
                    self._update_stats(doc.get("doc_type", ""))

                    if len(batch) >= batch_size:
                        await self._save_batch(batch)
                        batch = []
                        logger.info(
                            f"Progress: {self.stats['total_downloaded']} downloaded, "
                            f"{self.stats['total_skipped']} skipped, "
                            f"{self.stats['total_errors']} errors"
                        )
                        if self.progress_callback:
                            self.progress_callback(self.stats)

                self.stats["current_listing"] = f"Downloading ({self.stats['total_downloaded']}/{len(self.discovered_urls)})"

            # Save remaining batch
            if batch:
                await self._save_batch(batch)

        finally:
            self.running = False
            logger.info(f"Crawl complete. Stats: {json.dumps(self.stats, indent=2)}")

    def stop(self):
        self.running = False


# Singleton
_crawler: Optional[KenyaLawCrawler] = None


async def get_crawler() -> KenyaLawCrawler:
    global _crawler
    if _crawler is None:
        _crawler = KenyaLawCrawler()
    return _crawler


async def start_full_crawl():
    """Start the full site crawl in background."""
    crawler = await get_crawler()
    if crawler.running:
        return {"status": "already_running", "stats": crawler.stats}

    async def _run():
        async with crawler:
            await crawler.full_crawl()

    asyncio.create_task(_run())
    return {"status": "started", "stats": crawler.stats}


async def stop_crawl():
    crawler = await get_crawler()
    crawler.stop()
    return {"status": "stopping", "stats": crawler.stats}


async def get_crawl_progress():
    crawler = await get_crawler()
    return {
        "running": crawler.running,
        "stats": crawler.stats,
    }
