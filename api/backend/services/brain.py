"""
KenyaLaw Brain — instant local search over crawled legal data.

Loads metadata index + knowledge graph into memory for fast queries.
No external API calls needed — everything is local.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("juriscore")

# Brain data directory
BRAIN_DIR = os.getenv("BRAIN_DIR", "")

_data_loaded = False
_cases: List[Dict] = []
_legislation: List[Dict] = []
_gazettes: List[Dict] = []
_bills: List[Dict] = []
_articles: List[Dict] = []
_all_metadata: List[Dict] = []
_topic_cases: Dict[str, List] = {}
_topic_statutes: Dict[str, List] = {}
_court_hierarchy: Dict[str, Dict] = {}
_full_text_index: Dict[str, str] = {}


def _find_brain_dir() -> Optional[Path]:
    """Find the brain data directory."""
    if BRAIN_DIR and os.path.exists(BRAIN_DIR):
        return Path(BRAIN_DIR)

    # Resolve relative to this file's location (works on Vercel + local)
    here = Path(__file__).resolve().parent  # api/backend/services/
    data_dir = here / ".." / ".." / "data" / "brain"

    candidates = [
        data_dir,                          # api/backend/data/brain
        here / ".." / "data" / "brain",    # api/backend/data/brain (alt)
        Path("/tmp/brain"),                # Vercel temp fallback
    ]
    for p in candidates:
        if p.exists() and (p / "metadata" / "cases.json").exists():
            return p.resolve()
    return None


def load_brain() -> bool:
    """Load all brain data into memory. Returns True if successful."""
    global _data_loaded, _cases, _legislation, _gazettes, _bills, _articles
    global _all_metadata, _topic_cases, _topic_statutes, _court_hierarchy, _full_text_index

    if _data_loaded:
        return True

    brain_dir = _find_brain_dir()
    if not brain_dir:
        logger.warning("Brain data not found — falling back to live search")
        return False

    meta_dir = brain_dir / "metadata"
    graph_dir = brain_dir / "graph"

    try:
        # Load metadata
        with open(meta_dir / "cases.json", encoding="utf-8") as f:
            _cases = json.load(f)
        with open(meta_dir / "legislation.json", encoding="utf-8") as f:
            _legislation = json.load(f)
        with open(meta_dir / "gazettes.json", encoding="utf-8") as f:
            _gazettes = json.load(f)
        with open(meta_dir / "bills.json", encoding="utf-8") as f:
            _bills = json.load(f)
        with open(meta_dir / "articles.json", encoding="utf-8") as f:
            _articles = json.load(f)

        _all_metadata = _cases + _legislation + _gazettes + _bills + _articles

        # Load graph
        tc_path = graph_dir / "topic_cases.json"
        ts_path = graph_dir / "topic_statutes.json"
        ch_path = graph_dir / "court_hierarchy.json"
        ft_path = graph_dir / "full_text_index.json"

        if tc_path.exists():
            with open(tc_path, encoding="utf-8") as f:
                _topic_cases = json.load(f)
        if ts_path.exists():
            with open(ts_path, encoding="utf-8") as f:
                _topic_statutes = json.load(f)
        if ch_path.exists():
            with open(ch_path, encoding="utf-8") as f:
                _court_hierarchy = json.load(f)
        if ft_path.exists():
            with open(ft_path, encoding="utf-8") as f:
                _full_text_index = json.load(f)

        _data_loaded = True
        logger.info(
            f"Brain loaded: {len(_cases)} cases, {len(_legislation)} statutes, "
            f"{len(_gazettes)} gazettes, {len(_bills)} bills, {len(_articles)} articles"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to load brain data: {e}")
        return False


def _score_item(item: Dict, query_words: List[str]) -> float:
    """Score a metadata item against query words."""
    score = 0.0
    title = item.get("title", "").lower()
    excerpt = item.get("excerpt", "").lower()
    topics = " ".join(item.get("topics", [])).lower()
    citation = item.get("citation", "").lower()
    court = item.get("court", "").lower()

    for word in query_words:
        # Exact title match = highest
        if word in title:
            score += 10.0
        # Citation match
        if word in citation:
            score += 8.0
        # Court match
        if word in court:
            score += 5.0
        # Topic match
        if word in topics:
            score += 4.0
        # Excerpt match
        if word in excerpt:
            score += 2.0
        # Partial match
        for w2 in title.split():
            if word in w2 or w2 in word:
                score += 3.0
                break

    # Boost for recency
    year = item.get("year", 0)
    if year >= 2020:
        score *= 1.2
    elif year >= 2010:
        score *= 1.1

    # Boost for Supreme Court / Court of Appeal
    if court in ("supreme court", "court of appeal"):
        score *= 1.3

    return score


def brain_search(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    jurisdiction: str = "kenya",
    limit: int = 20,
) -> Dict[str, Any]:
    """
    Search the brain's local data. Returns results instantly without API calls.

    Args:
        query: Search query
        doc_type: Filter by document type (case, legislation, gazette, bill, article)
        court: Filter by court name
        jurisdiction: Always "kenya" for brain search
        limit: Max results

    Returns:
        Dict with count, results, source="brain"
    """
    if not _data_loaded:
        if not load_brain():
            return {"count": 0, "results": [], "source": "brain_unavailable"}

    query_words = [w.lower() for w in query.split() if len(w) > 1]
    if not query_words:
        return {"count": 0, "results": [], "source": "brain"}

    # Filter by doc_type
    if doc_type and doc_type != "all":
        type_map = {
            "cases": "case",
            "case": "case",
            "judgment": "case",
            "judgments": "case",
            "legislation": "legislation",
            "statute": "legislation",
            "act": "legislation",
            "gazette": "gazette",
            "gazettes": "gazette",
            "bill": "bill",
            "bills": "bill",
            "article": "article",
            "articles": "article",
        }
        target_type = type_map.get(doc_type.lower(), doc_type.lower())
        items = [i for i in _all_metadata if i.get("type") == target_type]
    else:
        items = _all_metadata

    # Filter by court
    if court and court.lower() != "all":
        court_lower = court.lower()
        items = [i for i in items if court_lower in (i.get("court", "") or "").lower()]

    # Score and rank
    scored = []
    for item in items:
        score = _score_item(item, query_words)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: -x[0])

    # Format results
    results = []
    for score, item in scored[:limit]:
        result = {
            "title": item.get("title", ""),
            "citation": item.get("citation", ""),
            "court": item.get("court", ""),
            "year": item.get("year", 0),
            "doc_type": item.get("type", "document"),
            "doc_type_label": item.get("type", "document").title(),
            "url": item.get("url", ""),
            "excerpt": item.get("excerpt", "")[:300],
            "topics": item.get("topics", []),
            "score": round(score / 10, 3),
            "source": "brain",
        }
        # Add full text if available
        url = item.get("url", "")
        if url and url in _full_text_index:
            result["full_text_available"] = True
        results.append(result)

    return {
        "count": len(results),
        "results": results,
        "source": "brain",
    }


def brain_get_case(title: str) -> Optional[Dict]:
    """Get a specific case by title (fuzzy match)."""
    if not _data_loaded:
        load_brain()

    title_lower = title.lower()
    for case in _cases:
        if title_lower in case.get("title", "").lower() or case.get("title", "").lower() in title_lower:
            result = dict(case)
            url = case.get("url", "")
            if url and url in _full_text_index:
                result["full_text"] = _full_text_index[url]
            return result
    return None


def brain_get_related_cases(topic: str, limit: int = 10) -> List[Dict]:
    """Get cases related to a topic."""
    if not _data_loaded:
        load_brain()

    topic_lower = topic.lower()

    # Direct topic lookup
    for topic_key, cases in _topic_cases.items():
        if topic_lower in topic_key.lower() or topic_key.lower() in topic_lower:
            return cases[:limit]

    # Fallback: search all cases by topic keywords
    results = []
    for case in _cases:
        case_topics = " ".join(case.get("topics", [])).lower()
        if topic_lower in case_topics:
            results.append({
                "title": case.get("title", ""),
                "citation": case.get("citation", ""),
                "court": case.get("court", ""),
                "year": case.get("year", 0),
                "url": case.get("url", ""),
            })
            if len(results) >= limit:
                break

    return results


def brain_get_statutes(topic: str, limit: int = 10) -> List[Dict]:
    """Get statutes related to a topic."""
    if not _data_loaded:
        load_brain()

    topic_lower = topic.lower()

    for topic_key, statutes in _topic_statutes.items():
        if topic_lower in topic_key.lower() or topic_key.lower() in topic_lower:
            return statutes[:limit]

    results = []
    for stat in _legislation:
        stat_topics = " ".join(stat.get("topics", [])).lower()
        if topic_lower in stat_topics:
            results.append({
                "title": stat.get("title", ""),
                "cap_number": stat.get("cap_number", ""),
                "year": stat.get("year", 0),
                "url": stat.get("url", ""),
            })
            if len(results) >= limit:
                break

    return results


def brain_get_court_info(court_name: str) -> Optional[Dict]:
    """Get court hierarchy information."""
    for name, info in _court_hierarchy.items():
        if court_name.lower() in name.lower() or name.lower() in court_name.lower():
            return {"court": name, **info}
    return None


def brain_get_constitution() -> Optional[Dict]:
    """Get the Constitution of Kenya 2010 from brain data."""
    if not _data_loaded:
        load_brain()

    for item in _legislation:
        if "constitution" in item.get("title", "").lower():
            result = dict(item)
            url = item.get("url", "")
            if url and url in _full_text_index:
                result["full_text"] = _full_text_index[url]
            return result

    # Return the hardcoded text if brain has no constitution
    return {
        "title": "Constitution of Kenya, 2010",
        "citation": "Cap. 16",
        "year": 2010,
        "url": "https://kenyalaw.org/kl/fileadmin/pdfdownloads/Constitutions/Constitution_of_Kenya_2010.pdf",
        "excerpt": "The supreme law of the Republic of Kenya providing for the structure of government, devolution, and bill of rights.",
        "topics": ["constitution", "supreme law", "bill of rights", "devolution"],
    }


def brain_get_statute(title: str) -> Optional[Dict]:
    """Get a specific statute by title (fuzzy match)."""
    if not _data_loaded:
        load_brain()

    title_lower = title.lower()
    for stat in _legislation:
        if title_lower in stat.get("title", "").lower() or stat.get("title", "").lower() in title_lower:
            return dict(stat)
    return None


def brain_get_all_courts() -> List[str]:
    """Get all court names from brain data."""
    if not _data_loaded:
        load_brain()
    return list(_court_hierarchy.keys())


def brain_get_all_doc_types() -> List[Dict]:
    """Get all document types with counts from brain data."""
    if not _data_loaded:
        load_brain()

    type_counts: Dict[str, int] = {}
    for item in _all_metadata:
        t = item.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    return [{"key": t, "count": c} for t, c in sorted(type_counts.items(), key=lambda x: -x[1])]


def brain_stats() -> Dict[str, Any]:
    """Get brain statistics."""
    if not _data_loaded:
        load_brain()

    return {
        "loaded": _data_loaded,
        "total_documents": len(_all_metadata),
        "cases": len(_cases),
        "legislation": len(_legislation),
        "gazettes": len(_gazettes),
        "bills": len(_bills),
        "articles": len(_articles),
        "topics": len(_topic_cases),
        "full_text_documents": len(_full_text_index),
    }
