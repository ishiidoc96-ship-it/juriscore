#!/usr/bin/env python
"""
Persistent KenyaLaw.org Crawler
Two-phase crawl: listings first (fast), then judgments (binary search).
Survives restarts by resuming from DB + progress files.

Usage:
    python run_crawler.py          # Run full crawl
    python run_crawler.py --status # Check progress
    python run_crawler.py --stop   # Signal stop
"""
import asyncio
import sys
import os
import json
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.expanduser("~"), "juriscore_crawler.log")),
    ],
)
logger = logging.getLogger("juriscore")


async def run_forever():
    """Run the crawl and keep the event loop alive."""
    from api.backend.services.kenyalaw_crawler import KenyaLawCrawler, _write_notification

    crawler = KenyaLawCrawler()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, crawler.stop)
        except NotImplementedError:
            pass

    _write_notification("running", "Crawler starting...", crawler._all_stats())

    async with crawler:
        await crawler.full_crawl()

    logger.info("Crawler finished.")


def show_status():
    from api.backend.services.kenyalaw_crawler import NOTIFICATION_FILE, PROGRESS_FILE

    print("=== KenyaLaw Crawler Status ===")

    # Try notification file first
    if NOTIFICATION_FILE.exists():
        try:
            n = json.loads(NOTIFICATION_FILE.read_text())
            status = n.get("status", "unknown")
            msg = n.get("message", "")
            print(f"\nNotification: {status} - {msg}")
            print(f"  Time: {n.get('timestamp', 'N/A')}")
        except Exception:
            print("\nNotification: (unreadable)")

    # Try progress file
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text())
            listings = data.get("listings", {})
            judgments = data.get("judgments", {})
            totals = data.get("totals", {})

            print(f"\n--- Phase 1: Listings ---")
            print(f"  Done: {listings.get('listings_done', 0)}/{listings.get('listings_total', 12)}")
            print(f"  Current: {listings.get('current_listing', 'N/A')} pg {listings.get('listing_page', 0)}")
            print(f"  URLs found: {listings.get('listing_urls_found', 0)}")
            print(f"  Downloaded: {listings.get('listing_downloaded', 0)}")
            print(f"  Skipped: {listings.get('listing_skipped', 0)}")
            print(f"  Errors: {listings.get('listing_errors', 0)}")

            print(f"\n--- Phase 2: Judgments ---")
            print(f"  Court: {judgments.get('current_court', 'N/A')} "
                  f"({judgments.get('courts_done', 0)}/{judgments.get('courts_total', 9)})")
            print(f"  Year: {judgments.get('current_year', 'N/A')} "
                  f"({judgments.get('years_done', 0)}/{judgments.get('years_total', 12)})")
            print(f"  Doc: {judgments.get('current_doc', 0)}/{judgments.get('max_docs', 0)}")
            print(f"  Downloaded: {judgments.get('judgments_downloaded', 0)}")
            print(f"  Skipped: {judgments.get('judgments_skipped', 0)}")
            print(f"  Errors: {judgments.get('judgments_errors', 0)}")

            print(f"\n--- Totals ---")
            print(f"  Saved: {totals.get('total_downloaded', 0)}")
            print(f"  Skipped: {totals.get('total_skipped', 0)}")
            print(f"  Errors: {totals.get('total_errors', 0)}")
            if totals.get("started_at"):
                print(f"  Started: {totals['started_at']}")
            if totals.get("completed_at"):
                print(f"  Completed: {totals['completed_at']}")
        except Exception as e:
            print(f"\nProgress file unreadable: {e}")

    # DB count
    try:
        import sqlite3
        db = os.path.join(os.environ.get("TEMP", ""), "juriscore.db")
        if os.path.exists(db):
            conn = sqlite3.connect(db)
            for table in ["kenyalaw_cases", "kenyalaw_legislation", "kenyalaw_articles"]:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    print(f"  DB {table}: {count}")
                except Exception:
                    pass
            conn.close()
    except Exception:
        pass


def stop_crawler():
    from api.backend.services.kenyalaw_crawler import NOTIFICATION_FILE, _ensure_dir
    _ensure_dir()
    NOTIFICATION_FILE.write_text(json.dumps({
        "status": "stopping",
        "message": "Stop signal sent",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }))
    print("Stop signal written. Crawler will stop after current document.")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--stop" in sys.argv:
        stop_crawler()
    else:
        asyncio.run(run_forever())
