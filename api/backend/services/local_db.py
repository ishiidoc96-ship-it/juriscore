"""
Local SQLite + FTS5 search database for instant legal search.
Loaded into memory at module import — searches in <10ms.
"""
import os
import sqlite3
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

_db_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "legal_db.sqlite")
_conn: Optional[sqlite3.Connection] = None
_ready = False


def _get_conn() -> sqlite3.Connection:
    global _conn, _ready
    if _conn is not None:
        return _conn
    if not os.path.exists(_db_path):
        logger.warning(f"Legal DB not found at {_db_path}")
        return None
    try:
        _conn = sqlite3.connect(_db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _ready = True
        count = _conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        logger.info(f"Legal DB loaded: {count} documents")
    except Exception as e:
        logger.error(f"Failed to load legal DB: {e}")
        _conn = None
    return _conn


def is_ready() -> bool:
    return _ready


def search_local_db(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    FTS5 full-text search on the local legal database.
    Returns results ranked by relevance in <10ms.
    """
    conn = _get_conn()
    if not conn:
        return []

    # Build FTS5 query — handle multi-word queries
    query_clean = re.sub(r'[^\w\s]', '', query.lower().strip())
    words = query_clean.split()
    if not words:
        return []

    # Use OR for broader matching, with phrase matching for exact matches
    fts_query = " OR ".join(words)

    try:
        # FTS5 search with ranking
        sql = """
            SELECT d.id, d.doc_type, d.title, d.citation, d.court, d.year,
                   d.topics, d.excerpt, d.url, d.date,
                   rank
            FROM documents d
            JOIN documents_fts fts ON d.id = fts.rowid
            WHERE documents_fts MATCH ?
        """
        params = [fts_query]

        if doc_type and doc_type != "all":
            sql += " AND d.doc_type = ?"
            params.append(doc_type)

        if court and court != "all":
            sql += " AND d.court LIKE ?"
            params.append(f"%{court}%")

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()

        results = []
        for row in rows:
            topics = row["topics"].split(",") if row["topics"] else []
            results.append({
                "id": f"db_{row['id']}",
                "doc_type": row["doc_type"],
                "title": row["title"],
                "citation": row["citation"],
                "court": row["court"],
                "year": row["year"],
                "date": row["date"] or "",
                "topics": topics,
                "excerpt": row["excerpt"] or "",
                "url": row["url"] or "",
                "score": abs(row["rank"]),
                "source": "local_db",
            })

        return results

    except Exception as e:
        logger.error(f"FTS5 search failed: {e}")
        # Fallback: simple LIKE search
        return _fallback_search(conn, query, doc_type, court, limit)


def _fallback_search(
    conn: sqlite3.Connection,
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Simple LIKE search as fallback when FTS5 fails."""
    try:
        words = query.lower().split()
        conditions = []
        params = []
        for w in words:
            conditions.append("(LOWER(title) LIKE ? OR LOWER(excerpt) LIKE ? OR LOWER(topics) LIKE ?)")
            params.extend([f"%{w}%", f"%{w}%", f"%{w}%"])

        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM documents WHERE {where}"

        if doc_type and doc_type != "all":
            sql += " AND doc_type = ?"
            params.append(doc_type)
        if court and court != "all":
            sql += " AND court LIKE ?"
            params.append(f"%{court}%")

        sql += " LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            topics = row["topics"].split(",") if row["topics"] else []
            results.append({
                "id": f"db_{row['id']}",
                "doc_type": row["doc_type"],
                "title": row["title"],
                "citation": row["citation"],
                "court": row["court"],
                "year": row["year"],
                "date": row["date"] or "",
                "topics": topics,
                "excerpt": row["excerpt"] or "",
                "url": row["url"] or "",
                "score": 0.5,
                "source": "local_db",
            })
        return results
    except Exception as e:
        logger.error(f"Fallback search failed: {e}")
        return []


def get_db_stats() -> Dict[str, Any]:
    """Return database statistics."""
    conn = _get_conn()
    if not conn:
        return {"ready": False, "count": 0}

    try:
        total = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        by_type = conn.execute(
            "SELECT doc_type, COUNT(*) as cnt FROM documents GROUP BY doc_type ORDER BY cnt DESC"
        ).fetchall()
        by_court = conn.execute(
            "SELECT court, COUNT(*) as cnt FROM documents GROUP BY court ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        return {
            "ready": True,
            "count": total,
            "by_type": {r["doc_type"]: r["cnt"] for r in by_type},
            "by_court": {r["court"]: r["cnt"] for r in by_court},
        }
    except Exception as e:
        return {"ready": False, "error": str(e)}
