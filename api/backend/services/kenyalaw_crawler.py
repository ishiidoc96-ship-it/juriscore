"""
KenyaLaw.org Full Site Crawler
Discovers and downloads every document from KenyaLaw.org.
Persists progress to survive restarts, sleep, and shutdown.
Resumes from where it left off automatically.
"""
import asyncio
import logging
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from pathlib import Path
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

KENYALAW_BASE = "https://www.kenyalaw.org"

# Rate limiting: 5 seconds per robots.txt Crawl-delay
RATE_LIMIT_DELAY = 5.0

# Persistence paths
PROGRESS_DIR = Path(tempfile.gettempdir()) / "juriscore_crawl"
PROGRESS_FILE = PROGRESS_DIR / "crawl_progress.json"
DISCOVERED_FILE = PROGRESS_DIR / "discovered_urls.json"
NOTIFICATION_FILE = PROGRESS_DIR / "crawl_notification.json"

# Kenyan courts
KENYAN_COURTS = [
    "KEHC", "KECA", "KESC", "KEELC", "KEELRC",
    "KEMC", "KEKC", "KEIC", "SCC",
]

# Years to crawl
YEARS = list(range(2026, 2014, -1))

# Max listing pages per court/year
MAX_LISTING_PAGES = 10

# All listing pages to crawl
LISTINGS = [
    *[(f"/judgments/{court}/", "judgment", f"Judgments - {court}") for court in KENYAN_COURTS],
    *[(f"/judgments/{court}/{year}/", "judgment", f"Judgments - {court} {year}")
      for court in KENYAN_COURTS for year in YEARS],
    ("/legislation/", "legislation", "Legislation (all)"),
    ("/legislation/recent", "legislation", "Legislation (recent)"),
    ("/legislation/counties", "legislation", "Legislation (counties)"),
    ("/articles/", "article", "Articles"),
    ("/bills/", "bill", "Bills"),
    ("/causelists/", "cause_list", "Cause Lists"),
    ("/gazettes/", "gazette", "Gazettes"),
    ("/taxonomy/collections", "article", "Collections"),
    ("/taxonomy/collections/collections-treaties", "treaty", "Treaties"),
    ("/taxonomy/elections", "article", "Elections"),
    ("/taxonomy/publications", "article", "Publications"),
    ("/taxonomy/foreign-legislation/foreign-legislation-east-african-community-eac",
     "legislation", "EAC Legislation"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _ensure_progress_dir():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)


def _load_progress() -> Dict:
    """Load crawl progress from disk."""
    _ensure_progress_dir()
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_progress(progress: Dict):
    """Save crawl progress to disk."""
    _ensure_progress_dir()
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def _load_discovered_urls() -> List[str]:
    """Load previously discovered URLs from disk."""
    _ensure_progress_dir()
    if DISCOVERED_FILE.exists():
        try:
            return json.loads(DISCOVERED_FILE.read_text())
        except Exception:
            pass
    return []


def _save_discovered_urls(urls: List[str]):
    """Save discovered URLs to disk."""
    _ensure_progress_dir()
    DISCOVERED_FILE.write_text(json.dumps(urls))


def _load_downloaded_urls_from_db() -> Set[str]:
    """Load already-downloaded URLs from the database."""
    try:
        import sqlite3
        import tempfile as tmp
        db_path = os.path.join(tmp.gettempdir(), "juriscore.db")
        if not os.path.exists(db_path):
            return set()
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT url FROM kenyalaw_cases WHERE url != ''")
        urls = {row[0] for row in cursor.fetchall()}
        cursor2 = conn.execute("SELECT url FROM kenyalaw_legislation WHERE url != ''")
        urls.update(row[0] for row in cursor2.fetchall())
        cursor3 = conn.execute("SELECT url FROM kenyalaw_articles WHERE url != ''")
        urls.update(row[0] for row in cursor3.fetchall())
        conn.close()
        logger.info(f"Loaded {len(urls)} already-downloaded URLs from database")
        return urls
    except Exception as e:
        logger.warning(f"Could not load URLs from DB: {e}")
        return set()


def _write_notification(status: str, message: str, stats: Dict = None):
    """Write a notification file for the frontend to pick up."""
    _ensure_progress_dir()
    NOTIFICATION_FILE.write_text(json.dumps({
        "status": status,
        "message": message,
        "stats": stats or {},
        "timestamp": datetime.utcnow().isoformat(),
    }))


class KenyaLawCrawler:
    """Full site crawler with resume support and persistence."""

    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.downloaded_urls: Set[str] = set()
        self.discovered_urls: List[str] = []
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
            "phase": "idle",
            "started_at": None,
            "completed_at": None,
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
        if not self.session:
            return None
        full_url = url if url.startswith("http") else f"{KENYALAW_BASE}{url}"
        for attempt in range(3):
            try:
                await self._rate_limit()
                response = await self.session.get(full_url)
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:
                    # Rate limited - back off
                    wait = 30 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.warning(f"HTTP {response.status_code} for {full_url}")
                    return None
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {full_url}: {e}")
                if attempt < 2:
                    await asyncio.sleep(10)
                else:
                    self.stats["total_errors"] += 1
                    return None

    def _extract_links_from_listing(self, html: str) -> List[str]:
        soup = BeautifulSoup(html, "lxml")
        links = []
        seen = set(self.discovered_urls)
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if "/akn/" in href:
                full = urljoin(KENYALAW_BASE, href).split("#")[0].strip()
                if full not in seen:
                    links.append(full)
                    seen.add(full)
        return links

    def _get_max_page(self, html: str) -> int:
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
        all_urls = []
        html = await self._fetch(listing_path)
        if not html:
            return all_urls

        urls = self._extract_links_from_listing(html)
        all_urls.extend(urls)
        self.discovered_urls.extend(urls)

        max_page = self._get_max_page(html)
        logger.info(f"Listing {listing_path}: {len(urls)} docs on page 1, max_page={max_page}")

        for pg in range(2, max_page + 1):
            if not self.running:
                break
            separator = "&" if "?" in listing_path else "?"
            page_url = f"{listing_path}{separator}page={pg}"
            html = await self._fetch(page_url)
            if html:
                urls = self._extract_links_from_listing(html)
                all_urls.extend(urls)
                self.discovered_urls.extend(urls)
                logger.info(f"  Page {pg}: {len(urls)} docs")

        return all_urls

    def _extract_document_data(self, html: str, url: str) -> Optional[Dict]:
        try:
            soup = BeautifulSoup(html, "lxml")

            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
                title = re.sub(r"\s*[-–]\s*Kenya\s*Law\s*$", "", title, flags=re.I)

            full_text = ""
            content = (soup.find("div", id="doc-content") or
                      soup.find("article") or
                      soup.find("div", class_="content") or
                      soup.find("main"))
            if content:
                full_text = content.get_text(separator="\n", strip=True)
            if not full_text:
                full_text = soup.get_text(separator="\n", strip=True)

            if not title and not full_text:
                return None

            doc_type = "judgment"
            if "/act/" in url or "/legislation/" in url:
                doc_type = "legislation"
            elif "/article" in url:
                doc_type = "article"
            elif "/bill/" in url:
                doc_type = "bill"
            elif "/judgment/" in url:
                doc_type = "judgment"

            court = ""
            court_match = re.search(r"/judgment/(ke\w+)/", url, re.I)
            if court_match:
                court = court_match.group(1).upper()

            year = 0
            year_match = re.search(r"/(\d{4})/", url)
            if year_match:
                year = int(year_match.group(1))

            doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
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
        html = await self._fetch(url)
        if html:
            return self._extract_document_data(html, url)
        return None

    async def _save_batch(self, documents: List[Dict]):
        if not documents:
            return
        from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
        await sync_live_results_to_db(documents)

    def _update_stats(self, doc_type: str, count: int = 1):
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

    def _save_state(self):
        """Persist current state to disk."""
        _save_progress(self.stats)
        # Save unique discovered URLs
        unique = list(dict.fromkeys(self.discovered_urls))
        _save_discovered_urls(unique)

    async def full_crawl(self):
        """Crawl the entire KenyaLaw.org site with full resume support."""
        self.running = True
        self.stats["started_at"] = datetime.utcnow().isoformat()
        self.stats["listings_total"] = len(LISTINGS)

        # Load previously downloaded URLs from DB
        self.downloaded_urls = _load_downloaded_urls_from_db()

        # Load previously discovered URLs from disk
        prev_discovered = _load_discovered_urls()
        if prev_discovered:
            self.discovered_urls = prev_discovered
            self.stats["total_discovered"] = len(prev_discovered)
            logger.info(f"Resuming: {len(prev_discovered)} URLs already discovered, "
                       f"{len(self.downloaded_urls)} already downloaded")

        _write_notification("running", "Crawl started", self.stats)
        logger.info(f"Starting KenyaLaw.org crawl ({len(LISTINGS)} listings)...")

        try:
            # Phase 1: Discover all URLs from listing pages
            if self.stats.get("phase") != "downloading":
                self.stats["phase"] = "discovering"
                logger.info("Phase 1: Discovering document URLs...")

                for i, (listing_path, doc_type, description) in enumerate(LISTINGS):
                    if not self.running:
                        self._save_state()
                        break

                    self.stats["current_listing"] = description
                    logger.info(f"[{i+1}/{len(LISTINGS)}] Crawling: {description}")

                    urls = await self._crawl_listing(listing_path, doc_type)
                    self.stats["total_discovered"] = len(self.discovered_urls)
                    self.stats["listings_done"] = i + 1

                    # Save state after each listing
                    self._save_state()

                    if self.progress_callback:
                        self.progress_callback(self.stats)

                    _write_notification("running",
                        f"Discovering: {description} ({i+1}/{len(LISTINGS)})",
                        self.stats)

                if self.running:
                    self.stats["phase"] = "downloading"
                    self._save_state()
                    logger.info(f"Phase 1 complete: {len(self.discovered_urls)} documents discovered")

            # Phase 2: Download each document
            if self.running:
                self.stats["phase"] = "downloading"
                logger.info("Phase 2: Downloading documents...")
                batch = []
                batch_size = 10

                # Filter out already-downloaded
                to_download = [u for u in self.discovered_urls if u not in self.downloaded_urls]
                logger.info(f"Need to download {len(to_download)} documents "
                           f"({len(self.downloaded_urls)} already in DB)")

                for idx, url in enumerate(to_download):
                    if not self.running:
                        self._save_state()
                        break

                    doc = await self._download_document(url)
                    if doc:
                        batch.append(doc)
                        self.downloaded_urls.add(url)
                        self._update_stats(doc.get("doc_type", ""))

                    # Save batch to DB periodically
                    if len(batch) >= batch_size:
                        await self._save_batch(batch)
                        batch = []
                        self._save_state()

                        total_done = self.stats["total_downloaded"] + self.stats["total_skipped"]
                        pct = (total_done / len(to_download) * 100) if to_download else 0
                        logger.info(
                            f"Progress: {self.stats['total_downloaded']} downloaded, "
                            f"{self.stats['total_skipped']} skipped, "
                            f"{pct:.1f}% complete"
                        )

                        _write_notification("running",
                            f"Downloading: {self.stats['total_downloaded']}/{len(to_download)} ({pct:.1f}%)",
                            self.stats)

                    self.stats["current_listing"] = (
                        f"Downloading ({self.stats['total_downloaded']}/{len(to_download)})")

                # Save final batch
                if batch:
                    await self._save_batch(batch)

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            _write_notification("error", f"Crawl error: {e}", self.stats)
        finally:
            self.running = False
            self.stats["completed_at"] = datetime.utcnow().isoformat()
            self._save_state()

            if self.stats["total_errors"] == 0 or self.stats["total_downloaded"] > 0:
                _write_notification("completed",
                    f"Crawl complete! {self.stats['total_downloaded']} documents downloaded.",
                    self.stats)
            else:
                _write_notification("stopped",
                    f"Crawl stopped. {self.stats['total_downloaded']} downloaded, "
                    f"{self.stats['total_errors']} errors.",
                    self.stats)

            logger.info(f"Crawl finished. Stats: {json.dumps(self.stats, indent=2)}")

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

    # Check for completion notification
    notification = None
    if NOTIFICATION_FILE.exists():
        try:
            notification = json.loads(NOTIFICATION_FILE.read_text())
        except Exception:
            pass

    # Load stats from disk if crawler isn't running
    stats = crawler.stats
    if not crawler.running:
        disk_stats = _load_progress()
        if disk_stats:
            stats = disk_stats

    return {
        "running": crawler.running,
        "stats": stats,
        "notification": notification,
    }


async def clear_crawl_state():
    """Clear all crawl progress (for fresh start)."""
    _ensure_progress_dir()
    for f in [PROGRESS_FILE, DISCOVERED_FILE, NOTIFICATION_FILE]:
        if f.exists():
            f.unlink()
    return {"status": "cleared"}
