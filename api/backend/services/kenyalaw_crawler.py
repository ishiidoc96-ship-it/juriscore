"""
KenyaLaw.org Full Site Crawler
Enumerates EVERY document using binary search on AKN URLs.
Persists progress to survive restarts. Resumes automatically.
"""
import asyncio
import logging
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from typing import Optional, Dict, List, Set
from pathlib import Path
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("juriscore")

KENYALAW_BASE = "https://www.kenyalaw.org"
RATE_LIMIT_DELAY = 5.0  # robots.txt Crawl-delay

# Persistence
PROGRESS_DIR = Path(tempfile.gettempdir()) / "juriscore_crawl"
PROGRESS_FILE = PROGRESS_DIR / "crawl_progress.json"
DOWNLOADED_FILE = PROGRESS_DIR / "downloaded_urls.json"
NOTIFICATION_FILE = PROGRESS_DIR / "crawl_notification.json"

KENYAN_COURTS = ["kehc", "keca", "kesc", "keelc", "keelrc", "kemc", "kekc", "keic", "scc"]
YEARS = list(range(2026, 2014, -1))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _ensure_dir():
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default if default is not None else {}


def _save_json(path: Path, data):
    _ensure_dir()
    path.write_text(json.dumps(data, indent=2))


def _load_downloaded_from_db() -> Set[str]:
    """Load already-downloaded URLs from SQLite."""
    try:
        import sqlite3
        db_path = os.path.join(tempfile.gettempdir(), "juriscore.db")
        if not os.path.exists(db_path):
            return set()
        conn = sqlite3.connect(db_path)
        urls = set()
        for table in ["kenyalaw_cases", "kenyalaw_legislation", "kenyalaw_articles"]:
            try:
                cursor = conn.execute(f"SELECT url FROM {table} WHERE url != ''")
                urls.update(row[0] for row in cursor.fetchall())
            except Exception:
                pass
        conn.close()
        return urls
    except Exception:
        return set()


def _write_notification(status: str, message: str, stats: Dict = None):
    _ensure_dir()
    NOTIFICATION_FILE.write_text(json.dumps({
        "status": status,
        "message": message,
        "stats": stats or {},
        "timestamp": datetime.utcnow().isoformat(),
    }))


class KenyaLawCrawler:
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.downloaded_urls: Set[str] = set()
        self.stats = {
            "phase": "idle",
            "total_downloaded": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "total_enumerated": 0,
            "judgments": 0,
            "legislation": 0,
            "articles": 0,
            "current_task": "",
            "courts_done": 0,
            "courts_total": 0,
            "years_done": 0,
            "years_total": 0,
            "started_at": None,
            "completed_at": None,
        }
        self.running = False

    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=HEADERS)
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
                r = await self.session.get(full_url)
                if r.status_code == 200:
                    return r.text
                elif r.status_code == 429:
                    await asyncio.sleep(30 * (attempt + 1))
                    continue
                else:
                    return None
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(10)
                else:
                    self.stats["total_errors"] += 1
                    return None

    async def _check_url_exists(self, url: str) -> bool:
        """HEAD request to check if URL exists (faster than full download)."""
        if not self.session:
            return False
        full_url = url if url.startswith("http") else f"{KENYALAW_BASE}{url}"
        try:
            await self._rate_limit()
            r = await self.session.head(full_url)
            return r.status_code == 200
        except Exception:
            return False

    async def _find_max_doc_number(self, court: str, year: int) -> int:
        """Binary search to find the max document number for a court/year."""
        lo, hi = 1, 50000
        # Quick check if any docs exist
        url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/1/eng"
        try:
            await self._rate_limit()
            r = await self.session.get(url)
            if r.status_code != 200:
                return 0
        except Exception:
            return 0

        while lo < hi:
            mid = (lo + hi + 1) // 2
            url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/{mid}/eng"
            try:
                await self._rate_limit()
                r = await self.session.get(url)
                if r.status_code == 200:
                    lo = mid
                else:
                    hi = mid - 1
            except Exception:
                hi = mid - 1

        return lo

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
                      soup.find("main"))
            if content:
                full_text = content.get_text(separator="\n", strip=True)
            if not full_text:
                full_text = soup.get_text(separator="\n", strip=True)

            if not title and not full_text:
                return None

            doc_type = "judgment"
            if "/act/" in url:
                doc_type = "legislation"

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
            logger.warning(f"Extract failed for {url}: {e}")
            self.stats["total_errors"] += 1
            return None

    async def _download_and_save(self, url: str) -> bool:
        """Download a document and save to DB. Returns True if new."""
        if url in self.downloaded_urls:
            self.stats["total_skipped"] += 1
            return False

        html = await self._fetch(url)
        if not html:
            self.stats["total_errors"] += 1
            return False

        doc = self._extract_document_data(html, url)
        if not doc:
            return False

        from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
        await sync_live_results_to_db([doc])
        self.downloaded_urls.add(url)
        self.stats["total_downloaded"] += 1

        dt = doc.get("doc_type", "")
        if dt == "judgment":
            self.stats["judgments"] += 1
        elif dt == "legislation":
            self.stats["legislation"] += 1
        else:
            self.stats["articles"] += 1

        return True

    def _save_state(self):
        _save_json(PROGRESS_FILE, self.stats)
        _save_json(DOWNLOADED_FILE, list(self.downloaded_urls))

    async def _crawl_court_year(self, court: str, year: int):
        """Enumerate and download all judgments for a court/year."""
        max_num = await self._find_max_doc_number(court, year)
        if max_num == 0:
            return

        logger.info(f"{court} {year}: {max_num} documents found")
        self.stats["total_enumerated"] += max_num

        for num in range(1, max_num + 1):
            if not self.running:
                return

            url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/{num}/eng"
            await self._download_and_save(url)

            if self.stats["total_downloaded"] % 50 == 0:
                self._save_state()
                _write_notification("running",
                    f"Downloading {court} {year}: doc {num}/{max_num} "
                    f"({self.stats['total_downloaded']} total saved)",
                    self.stats)

    async def _crawl_listing_pages(self):
        """Crawl listing pages for legislation, articles, bills, etc."""
        listings = [
            ("/legislation/", "legislation"),
            ("/legislation/recent", "legislation"),
            ("/legislation/counties", "legislation"),
            ("/articles/", "article"),
            ("/bills/", "bill"),
            ("/causelists/", "cause_list"),
            ("/gazettes/", "gazette"),
            ("/taxonomy/collections", "article"),
            ("/taxonomy/collections/collections-treaties", "treaty"),
            ("/taxonomy/elections", "article"),
            ("/taxonomy/publications", "article"),
            ("/taxonomy/foreign-legislation/foreign-legislation-east-african-community-eac",
             "legislation"),
        ]

        for listing_path, doc_type in listings:
            if not self.running:
                return

            self.stats["current_task"] = f"Listing: {listing_path}"
            logger.info(f"Crawling listing: {listing_path}")

            html = await self._fetch(listing_path)
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            links = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if "/akn/" in href:
                    full = urljoin(KENYALAW_BASE, href).split("#")[0].strip()
                    links.add(full)

            # Get pagination
            max_page = 1
            for a in soup.find_all("a", href=True):
                m = re.search(r"page=(\d+)", a["href"])
                if m:
                    pg = int(m.group(1))
                    if pg > max_page:
                        max_page = pg
            max_page = min(max_page, 10)

            for pg in range(2, max_page + 1):
                if not self.running:
                    return
                sep = "&" if "?" in listing_path else "?"
                html = await self._fetch(f"{listing_path}{sep}page={pg}")
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a["href"].strip()
                        if "/akn/" in href:
                            full = urljoin(KENYALAW_BASE, href).split("#")[0].strip()
                            links.add(full)

            logger.info(f"  Found {len(links)} links from {listing_path}")
            for url in links:
                if not self.running:
                    return
                await self._download_and_save(url)

    async def full_crawl(self):
        self.running = True
        self.stats["started_at"] = datetime.utcnow().isoformat()
        self.stats["phase"] = "enumerating"

        # Resume: load already-downloaded URLs
        self.downloaded_urls = _load_downloaded_from_db()
        prev = _load_json(DOWNLOADED_FILE, [])
        self.downloaded_urls.update(prev)
        logger.info(f"Resuming: {len(self.downloaded_urls)} URLs already downloaded")

        _write_notification("running", "Crawl started", self.stats)

        try:
            # Phase 1: Enumerate and download all judgments by court/year
            self.stats["courts_total"] = len(KENYAN_COURTS)
            self.stats["years_total"] = len(YEARS)

            for ci, court in enumerate(KENYAN_COURTS):
                if not self.running:
                    break
                self.stats["courts_done"] = ci
                logger.info(f"=== Court {ci+1}/{len(KENYAN_COURTS)}: {court.upper()} ===")

                for yi, year in enumerate(YEARS):
                    if not self.running:
                        break
                    self.stats["years_done"] = yi
                    self.stats["current_task"] = f"{court.upper()} {year}"

                    await self._crawl_court_year(court, year)
                    self._save_state()

            # Phase 2: Crawl listing pages for non-judgment content
            if self.running:
                self.stats["phase"] = "listings"
                await self._crawl_listing_pages()

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            _write_notification("error", f"Error: {e}", self.stats)
        finally:
            self.running = False
            self.stats["completed_at"] = datetime.utcnow().isoformat()
            self._save_state()
            _write_notification("completed",
                f"Crawl complete! {self.stats['total_downloaded']} documents saved.",
                self.stats)
            logger.info(f"Crawl finished: {json.dumps(self.stats, indent=2)}")

    def stop(self):
        self.running = False


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
    notification = None
    if NOTIFICATION_FILE.exists():
        try:
            notification = json.loads(NOTIFICATION_FILE.read_text())
        except Exception:
            pass
    stats = crawler.stats
    if not crawler.running:
        disk_stats = _load_json(PROGRESS_FILE)
        if disk_stats:
            stats = disk_stats
    return {"running": crawler.running, "stats": stats, "notification": notification}


async def clear_crawl_state():
    _ensure_dir()
    for f in [PROGRESS_FILE, DOWNLOADED_FILE, NOTIFICATION_FILE]:
        if f.exists():
            f.unlink()
    return {"status": "cleared"}
