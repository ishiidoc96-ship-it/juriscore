"""
In-memory FTS5-compatible search for 12,000+ Kenyan legal cases.
Uses compressed base64 data file — no SQLite dependency on Vercel.
"""
import base64, gzip, json, os, re, logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

_data: List[Dict] = []
_index: Dict[str, List[int]] = {}
_ready = False


def _load_data():
    global _data, _index, _ready
    if _ready:
        return

    # Try base64 compressed file first (Vercel)
    b64_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cases.json.gz.b64")
    # Try SQLite as fallback (local dev)
    sqlite_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "legal_db.sqlite")

    if os.path.exists(b64_path):
        try:
            with open(b64_path, "r") as f:
                b64 = f.read()
            raw = gzip.decompress(base64.b64decode(b64))
            _data = json.loads(raw)
            logger.info(f"Loaded {len(_data)} cases from base64 file")
        except Exception as e:
            logger.error(f"Failed to load base64 data: {e}")
    elif os.path.exists(sqlite_path):
        try:
            import sqlite3
            conn = sqlite3.connect(sqlite_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM documents").fetchall()
            _data = [dict(r) for r in rows]
            conn.close()
            logger.info(f"Loaded {len(_data)} cases from SQLite")
        except Exception as e:
            logger.error(f"Failed to load SQLite: {e}")
    else:
        logger.warning("No case data found")
        _ready = True
        return

    # Build inverted index for fast search
    _index = {}
    for i, case in enumerate(_data):
        text = " ".join([
            case.get("title", ""),
            case.get("citation", ""),
            case.get("court", ""),
            case.get("topics", "") if isinstance(case.get("topics", ""), str) else " ".join(case.get("topics", [])),
            case.get("excerpt", ""),
        ]).lower()
        words = set(re.findall(r'\w+', text))
        for w in words:
            if len(w) > 1:
                if w not in _index:
                    _index[w] = []
                _index[w].append(i)

    _ready = True
    logger.info(f"Search index built: {len(_index)} terms, {len(_data)} documents")


def is_ready() -> bool:
    _load_data()
    return _ready


def search_local_db(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    _load_data()
    if not _data:
        return []

    query_clean = re.sub(r'[^\w\s]', '', query.lower().strip())
    words = query_clean.split()
    if not words:
        return []

    # TF-IDF-like scoring with field weighting
    scores: Dict[int, float] = {}
    doc_count = len(_data)

    # Calculate IDF for each query word
    idf = {}
    for w in words:
        if w in _index:
            df = len(_index[w])
            idf[w] = max(0.1, 1.0 + (doc_count / (1 + df)))
        else:
            idf[w] = 0

    # Score documents with field-weighted TF-IDF
    for w in words:
        if w in _index:
            for idx in _index[w]:
                case = _data[idx]
                tf = 1.0  # term frequency (binary)

                # Field weighting: title > citation > court > topics > excerpt
                field_weight = 1.0
                title = case.get("title", "").lower()
                citation = case.get("citation", "").lower()
                court = case.get("court", "").lower()
                topics_raw = case.get("topics", "")
                topics = topics_raw.lower() if isinstance(topics_raw, str) else " ".join(topics_raw).lower() if isinstance(topics_raw, list) else ""
                excerpt = case.get("excerpt", "").lower()

                if w in title:
                    field_weight = 3.0  # Title match = 3x
                elif w in citation:
                    field_weight = 2.5  # Citation match = 2.5x
                elif w in court:
                    field_weight = 2.0  # Court match = 2x
                elif w in topics:
                    field_weight = 1.8  # Topic match = 1.8x
                elif w in excerpt:
                    field_weight = 1.0  # Excerpt match = 1x

                scores[idx] = scores.get(idx, 0) + (tf * idf[w] * field_weight)

    # Phrase matching bonus: if multi-word query appears as phrase
    if len(words) > 1:
        full_phrase = " ".join(words)
        for i, case in enumerate(_data):
            text = " ".join([
                case.get("title", ""),
                case.get("citation", ""),
                case.get("excerpt", ""),
            ]).lower()
            if full_phrase in text:
                scores[i] = scores.get(i, 0) + 5.0  # Big bonus for exact phrase

    # Sort by score descending
    scored = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in scored:
        if len(results) >= limit:
            break

        case = _data[idx]

        # Apply filters
        if doc_type and doc_type != "all":
            case_type = case.get("doc_type", "")
            if case_type != doc_type:
                continue

        if court and court != "all":
            case_court = case.get("court", "")
            if court.lower() not in case_court.lower():
                continue

        topics = case.get("topics", "")
        if isinstance(topics, str):
            topics = [t.strip() for t in topics.split(",") if t.strip()]

        results.append({
            "id": f"db_{idx}",
            "doc_type": case.get("doc_type", "judgment"),
            "title": case.get("title", ""),
            "citation": case.get("citation", ""),
            "court": case.get("court", ""),
            "year": case.get("year", 0),
            "date": case.get("date", ""),
            "topics": topics,
            "excerpt": case.get("excerpt", ""),
            "url": case.get("url", ""),
            "score": score,
            "source": "local_db",
        })

    return results


def get_db_stats() -> Dict[str, Any]:
    _load_data()
    if not _data:
        return {"ready": False, "count": 0}

    by_type: Dict[str, int] = {}
    by_court: Dict[str, int] = {}
    for case in _data:
        dt = case.get("doc_type", "unknown")
        by_type[dt] = by_type.get(dt, 0) + 1
        c = case.get("court", "unknown")
        by_court[c] = by_court.get(c, 0) + 1

    years = [c.get("year", 0) for c in _data if c.get("year", 0) > 0]

    return {
        "ready": True,
        "count": len(_data),
        "index_terms": len(_index),
        "by_type": dict(sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:10]),
        "by_court": dict(sorted(by_court.items(), key=lambda x: x[1], reverse=True)[:10]),
        "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
    }
