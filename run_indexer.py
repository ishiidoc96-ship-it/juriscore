#!/usr/bin/env python
"""
Vector Index Builder for Juriscore
Indexes all documents from SQLite into zvec for semantic search.

Usage:
    python run_indexer.py          # Index all documents
    python run_indexer.py --stats  # Show index stats
"""
import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("juriscore")


def show_stats():
    from api.backend.services.vector_search import get_index_stats
    stats = get_index_stats()
    print("=== Vector Index Stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # DB counts
    import sqlite3
    import tempfile
    db_path = os.path.join(tempfile.gettempdir(), "juriscore.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        for table in ["kenyalaw_cases", "kenyalaw_legislation", "kenyalaw_articles"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"  DB {table}: {count}")
            except Exception:
                pass
        conn.close()


async def run_index():
    from api.backend.services.vector_search import index_from_database

    logger.info("Starting vector index build...")
    count = await index_from_database()
    logger.info(f"Indexed {count} documents into vector database")

    # Show stats
    show_stats()


if __name__ == "__main__":
    if "--stats" in sys.argv:
        show_stats()
    else:
        asyncio.run(run_index())
