"""
KenyaLaw.org Crawler v3 - Organized Two-Phase Approach
Phase 1: Listing pages (legislation, bills, articles, etc.) - FAST
Phase 2: Binary search for judgments per court/year - SLOW
Progress tracked per-phase with full resume support.
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
RATE_LIMIT_DELAY = 3.0
MAX_CONCURRENT = 3

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

# Listing pages: (path, max_pages, description)
LISTINGS = [
    ("/legislation/", 10, "Legislation"),
    ("/legislation/recent", 5, "Recent Legislation"),
    ("/legislation/counties", 5, "County Legislation"),
    ("/bills/", 10, "Bills"),
    ("/causelists/", 5, "Cause Lists"),
    ("/gazettes/", 5, "Gazettes"),
    ("/taxonomy/collections", 5, "Collections"),
    ("/taxonomy/collections/collections-treaties", 3, "Treaties"),
    ("/taxonomy/elections", 3, "Elections"),
    ("/taxonomy/publications", 3, "Publications"),
    ("/taxonomy/publications/publications-case-digests", 1, "Case Digests"),
    ("/taxonomy/publications/publications-kenya-law-reports", 1, "Law Reports"),
    ("/taxonomy/publications/publications-bench-bulletin", 2, "Bench Bulletin"),
    ("/taxonomy/publications/publications-annual-report", 1, "Annual Reports"),
    ("/taxonomy/publications/publications-commission-reports", 2, "Commission Reports"),
    ("/taxonomy/publications/publications-journals", 1, "Journals"),
    ("/taxonomy/publications/publications-law-related-articles", 2, "Law Related Articles"),
    ("/taxonomy/foreign-legislation/foreign-legislation-east-african-community-eac", 3, "EAC Foreign Legislation"),
    ("/articles/", 55, "Articles"),
]


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
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.running = False
        self.stop_requested = False

        # Phase 1 stats (listings)
        self.p1 = {
            "phase": "listings",
            "listings_done": 0,
            "listings_total": len(LISTINGS),
            "current_listing": "",
            "listing_page": 0,
            "listing_max_pages": 0,
            "listing_urls_found": 0,
            "listing_downloaded": 0,
            "listing_skipped": 0,
            "listing_errors": 0,
        }

        # Phase 2 stats (judgments)
        self.p2 = {
            "phase": "judgments",
            "courts_done": 0,
            "courts_total": len(KENYAN_COURTS),
            "current_court": "",
            "years_done": 0,
            "years_total": len(YEARS),
            "current_year": 0,
            "current_doc": 0,
            "max_docs": 0,
            "judgments_downloaded": 0,
            "judgments_skipped": 0,
            "judgments_errors": 0,
        }

        # Global stats
        self.stats = {
            "total_downloaded": 0,
            "total_skipped": 0,
            "total_errors": 0,
            "started_at": None,
            "completed_at": None,
        }

    def _all_stats(self) -> Dict:
        return {
            "listings": self.p1,
            "judgments": self.p2,
            "totals": self.stats,
        }

    async def __aenter__(self):
        self.session = httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=HEADERS)
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.aclose()

    def stop(self):
        self.stop_requested = True

    async def _rate_limit(self):
        await asyncio.sleep(RATE_LIMIT_DELAY)

    async def _fetch(self, url: str) -> Optional[str]:
        if not self.session or self.stop_requested:
            return None
        full_url = url if url.startswith("http") else f"{KENYALAW_BASE}{url}"
        for attempt in range(3):
            try:
                async with self.semaphore:
                    await self._rate_limit()
                    r = await self.session.get(full_url)
                    if r.status_code == 200:
                        return r.text
                    elif r.status_code == 429:
                        await asyncio.sleep(30 * (attempt + 1))
                    else:
                        return None
            except Exception:
                if attempt < 2:
                    await asyncio.sleep(10)
                else:
                    self.stats["total_errors"] += 1
                    return None

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
            if "/act/" in url or "/bill/" in url:
                doc_type = "legislation"
            elif "/article" in url:
                doc_type = "article"
            elif "/gazette" in url:
                doc_type = "gazette"
            elif "/doc/case-digest" in url:
                doc_type = "case_digest"
            elif "/doc/" in url:
                doc_type = "publication"

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
            logger.warning(f"Extract failed: {e}")
            self.stats["total_errors"] += 1
            return None

    async def _download_and_save(self, url: str) -> bool:
        if url in self.downloaded_urls:
            return False

        html = await self._fetch(url)
        if not html:
            return False

        doc = self._extract_document_data(html, url)
        if not doc:
            return False

        try:
            from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
            await sync_live_results_to_db([doc])
        except Exception as e:
            logger.warning(f"DB save failed: {e}")
            return False

        self.downloaded_urls.add(url)
        self.stats["total_downloaded"] += 1
        return True

    def _save_state(self):
        _save_json(PROGRESS_FILE, self._all_stats())
        _save_json(DOWNLOADED_FILE, list(self.downloaded_urls))

    def _notify(self, msg: str):
        _write_notification("running", msg, self._all_stats())

    # ── Phase 1: Listing pages ──

    async def _crawl_listing_pages(self):
        self.p1["listings_total"] = len(LISTINGS)

        for li, (path, max_pages, desc) in enumerate(LISTINGS):
            if self.stop_requested:
                break

            self.p1["listings_done"] = li
            self.p1["current_listing"] = desc
            self.p1["listing_max_pages"] = max_pages
            self._notify(f"Phase 1: {desc} ({li+1}/{len(LISTINGS)})")

            all_urls = set()

            for pg in range(1, max_pages + 1):
                if self.stop_requested:
                    break

                self.p1["listing_page"] = pg
                sep = "&" if "?" in path else "?"
                url = f"{path}{sep}page={pg}" if pg > 1 else path

                html = await self._fetch(url)
                if not html:
                    break

                soup = BeautifulSoup(html, "lxml")
                page_urls = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if "/akn/" in href:
                        full = urljoin(KENYALAW_BASE, href).split("#")[0].split("?")[0].strip()
                        if full not in all_urls:
                            page_urls.add(full)
                            all_urls.add(full)

                if not page_urls:
                    break

                self.p1["listing_urls_found"] = len(all_urls)
                logger.info(f"  {desc} pg {pg}: +{len(page_urls)} = {len(all_urls)} total")
                self._notify(f"Phase 1: {desc} pg {pg}/{max_pages} ({len(all_urls)} urls)")

            # Download all found URLs
            logger.info(f"  Downloading {len(all_urls)} URLs from {desc}")
            for i, url in enumerate(all_urls):
                if self.stop_requested:
                    break

                saved = await self._download_and_save(url)
                if saved:
                    self.p1["listing_downloaded"] += 1
                elif url in self.downloaded_urls:
                    self.p1["listing_skipped"] += 1
                else:
                    self.p1["listing_errors"] += 1

                if (i + 1) % 25 == 0:
                    self._save_state()
                    self._notify(
                        f"Phase 1: {desc} downloading {i+1}/{len(all_urls)} "
                        f"({self.stats['total_downloaded']} total saved)"
                    )

            self._save_state()
            logger.info(f"  Done {desc}: {len(all_urls)} urls, "
                       f"{self.p1['listing_downloaded']} new saved")

        self.p1["listings_done"] = len(LISTINGS)
        self._notify(f"Phase 1 complete: {self.stats['total_downloaded']} documents saved")

    # ── Phase 2: Binary search for judgments ──

    async def _find_max_doc_number(self, court: str, year: int) -> int:
        lo, hi = 1, 50000
        url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/1/eng"
        try:
            async with self.semaphore:
                await self._rate_limit()
                r = await self.session.get(url)
                if r.status_code != 200:
                    return 0
        except Exception:
            return 0

        while lo < hi:
            if self.stop_requested:
                return lo
            mid = (lo + hi + 1) // 2
            url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/{mid}/eng"
            try:
                async with self.semaphore:
                    await self._rate_limit()
                    r = await self.session.get(url)
                    if r.status_code == 200:
                        lo = mid
                    else:
                        hi = mid - 1
            except Exception:
                hi = mid - 1

        return lo

    async def _crawl_judgments(self):
        self.p2["courts_total"] = len(KENYAN_COURTS)
        self.p2["years_total"] = len(YEARS)

        for ci, court in enumerate(KENYAN_COURTS):
            if self.stop_requested:
                break

            self.p2["courts_done"] = ci
            self.p2["current_court"] = court.upper()
            self._notify(f"Phase 2: {court.upper()} ({ci+1}/{len(KENYAN_COURTS)} courts)")

            for yi, year in enumerate(YEARS):
                if self.stop_requested:
                    break

                self.p2["years_done"] = yi
                self.p2["current_year"] = year

                # Binary search
                self._notify(f"Phase 2: Searching {court.upper()} {year}...")
                max_num = await self._find_max_doc_number(court, year)
                if max_num == 0:
                    continue

                self.p2["max_docs"] = max_num
                logger.info(f"{court.upper()} {year}: {max_num} documents")

                for num in range(1, max_num + 1):
                    if self.stop_requested:
                        return

                    self.p2["current_doc"] = num
                    url = f"{KENYALAW_BASE}/akn/ke/judgment/{court}/{year}/{num}/eng"

                    saved = await self._download_and_save(url)
                    if saved:
                        self.p2["judgments_downloaded"] += 1
                    elif url in self.downloaded_urls:
                        self.p2["judgments_skipped"] += 1
                    else:
                        self.p2["judgments_errors"] += 1

                    if self.stats["total_downloaded"] % 25 == 0:
                        self._save_state()
                        self._notify(
                            f"Phase 2: {court.upper()} {year} doc {num}/{max_num} "
                            f"({self.stats['total_downloaded']} total saved)"
                        )

                self._save_state()

        self._notify(f"Phase 2 complete: {self.stats['total_downloaded']} total saved")

    # ── Main crawl ──

    async def full_crawl(self):
        self.running = True
        self.stats["started_at"] = datetime.utcnow().isoformat()

        # Ensure DB tables
        try:
            from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
        except Exception:
            pass

        try:
            from api.backend.models.database import engine
            from sqlalchemy import text
            async with engine.begin() as conn:
                for ddl in [
                    """CREATE TABLE IF NOT EXISTS kenyalaw_cases (
                        id TEXT PRIMARY KEY, title TEXT, citation TEXT, court TEXT,
                        year INTEGER, doc_type TEXT, excerpt TEXT, url TEXT,
                        search_url TEXT, topics TEXT, judges TEXT, case_number TEXT,
                        full_text TEXT, score REAL, last_synced DATETIME,
                        created_at DATETIME, updated_at DATETIME
                    )""",
                    """CREATE TABLE IF NOT EXISTS kenyalaw_legislation (
                        id TEXT PRIMARY KEY, title TEXT, citation TEXT,
                        act_number TEXT, year INTEGER, doc_type TEXT, excerpt TEXT,
                        url TEXT, full_text TEXT, last_synced DATETIME,
                        created_at DATETIME
                    )""",
                    """CREATE TABLE IF NOT EXISTS kenyalaw_articles (
                        id TEXT PRIMARY KEY, title TEXT, author TEXT, date TEXT,
                        doc_type TEXT, excerpt TEXT, url TEXT, full_text TEXT,
                        last_synced DATETIME, created_at DATETIME
                    )""",
                    "CREATE INDEX IF NOT EXISTS ix_klc_url ON kenyalaw_cases(url)",
                    "CREATE INDEX IF NOT EXISTS ix_klc_court ON kenyalaw_cases(court)",
                    "CREATE INDEX IF NOT EXISTS ix_klc_year ON kenyalaw_cases(year)",
                    "CREATE INDEX IF NOT EXISTS ix_kll_url ON kenyalaw_legislation(url)",
                    "CREATE INDEX IF NOT EXISTS ix_kla_url ON kenyalaw_articles(url)",
                ]:
                    await conn.execute(text(ddl))
            logger.info("DB tables ensured")
        except Exception as e:
            logger.warning(f"DB init warning: {e}")

        # Resume from DB + progress files
        self.downloaded_urls = _load_downloaded_from_db()
        prev = _load_json(DOWNLOADED_FILE, [])
        self.downloaded_urls.update(prev)
        logger.info(f"Resuming: {len(self.downloaded_urls)} URLs already downloaded")

        _write_notification("running", "Crawl started", self._all_stats())

        try:
            # Phase 1: Listing pages (fast)
            logger.info("=== PHASE 1: Listing Pages ===")
            await self._crawl_listing_pages()

            # Phase 2: Judgments (slow)
            if not self.stop_requested:
                logger.info("=== PHASE 2: Judgments (Binary Search) ===")
                await self._crawl_judgments()

        except Exception as e:
            logger.error(f"Crawl error: {e}")
            _write_notification("error", f"Error: {e}", self._all_stats())
        finally:
            self.running = False
            self.stats["completed_at"] = datetime.utcnow().isoformat()
            self._save_state()
            _write_notification("completed",
                f"Done! {self.stats['total_downloaded']} documents saved.",
                self._all_stats())
            logger.info("Crawl finished")


# ── Module-level API ──

_crawler: Optional[KenyaLawCrawler] = None


async def get_crawler() -> KenyaLawCrawler:
    global _crawler
    if _crawler is None:
        _crawler = KenyaLawCrawler()
    return _crawler


async def start_full_crawl():
    crawler = await get_crawler()
    if crawler.running:
        return {"status": "already_running", "stats": crawler._all_stats()}

    async def _run():
        async with crawler:
            await crawler.full_crawl()

    asyncio.create_task(_run())
    return {"status": "started", "stats": crawler._all_stats()}


async def stop_crawl():
    crawler = await get_crawler()
    crawler.stop()
    return {"status": "stopping", "stats": crawler._all_stats()}


async def get_crawl_progress():
    crawler = await get_crawler()
    notification = None
    if NOTIFICATION_FILE.exists():
        try:
            notification = json.loads(NOTIFICATION_FILE.read_text())
        except Exception:
            pass
    stats = crawler._all_stats() if crawler.running else _load_json(PROGRESS_FILE, {})
    return {"running": crawler.running, "stats": stats, "notification": notification}


async def clear_crawl_state():
    _ensure_dir()
    for f in [PROGRESS_FILE, DOWNLOADED_FILE, NOTIFICATION_FILE]:
        if f.exists():
            f.unlink()
    return {"status": "cleared"}
