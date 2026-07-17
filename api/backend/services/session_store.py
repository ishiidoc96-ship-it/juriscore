"""
Persistent session store — JSON file-based storage with Cloudinary backup.
Works on Vercel (/tmp) and locally. Sessions persist across server restarts.
"""
import json
import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

logger = logging.getLogger("juriscore")

# Storage paths
LOCAL_DIR = Path(os.getenv("SESSION_DIR", "/tmp/juriscore_sessions"))
LOCAL_DIR.mkdir(parents=True, exist_ok=True)

# Session TTL (7 days)
SESSION_TTL_DAYS = 7


def _session_path(session_id: str) -> Path:
    """Get the file path for a session."""
    safe_id = session_id.replace("/", "_").replace("\\", "_")
    return LOCAL_DIR / f"{safe_id}.json"


def save_session(session_id: str, session: Dict[str, Any]) -> bool:
    """Save a session to disk."""
    try:
        session["last_saved"] = datetime.utcnow().isoformat()
        path = _session_path(session_id)
        path.write_text(json.dumps(session, default=str, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning(f"Failed to save session {session_id}: {e}")
        return False


def load_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Load a session from disk."""
    try:
        path = _session_path(session_id)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
    except Exception as e:
        logger.warning(f"Failed to load session {session_id}: {e}")
    return None


def delete_session(session_id: str) -> bool:
    """Delete a session from disk."""
    try:
        path = _session_path(session_id)
        if path.exists():
            path.unlink()
            return True
    except Exception as e:
        logger.warning(f"Failed to delete session {session_id}: {e}")
    return False


def list_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """List all sessions from disk."""
    sessions = []
    try:
        for path in LOCAL_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("id"),
                    "message_count": len(data.get("messages", [])),
                    "created_at": data.get("created_at"),
                    "last_active": data.get("last_active"),
                    "last_saved": data.get("last_saved"),
                    "topic_summary": data.get("context", {}).get("topic_summary", ""),
                })
            except Exception:
                continue
        sessions.sort(key=lambda s: s.get("last_active") or "", reverse=True)
    except Exception as e:
        logger.warning(f"Failed to list sessions: {e}")
    return sessions[:limit]


def cleanup_old_sessions(days: int = SESSION_TTL_DAYS) -> int:
    """Delete sessions older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    removed = 0
    try:
        for path in LOCAL_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                last_active = data.get("last_active", "")
                if last_active:
                    last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00").replace("+00:00", ""))
                    if last_dt < cutoff:
                        path.unlink()
                        removed += 1
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")
    return removed


# ── Learning & Context Extraction ─────────────────────────────────────────────

def extract_session_context(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract learning context from conversation messages."""
    context = {
        "topics_discussed": [],
        "cases_referenced": [],
        "statutes_referenced": [],
        "search_queries": [],
        "question_types": [],
    }

    for msg in messages:
        if msg.get("role") != "user":
            continue

        content = msg.get("content", "").lower()

        # Track search queries
        if any(kw in content for kw in ["search", "find", "look up", "show me"]):
            context["search_queries"].append(msg.get("content", ""))

        # Track legal topics
        topic_keywords = [
            "contract", "tort", "criminal", "constitutional", "administrative",
            "property", "family", "commercial", "labor", "environmental",
            "negligence", "trespass", "nuisance", "defamation", "fraud",
        ]
        for topic in topic_keywords:
            if topic in content and topic not in context["topics_discussed"]:
                context["topics_discussed"].append(topic)

        # Track case references (basic pattern)
        import re
        case_pattern = r'\b\w+\s+v[s]?\s+\w+\b'
        cases = re.findall(case_pattern, msg.get("content", ""))
        for case in cases:
            if case not in context["cases_referenced"]:
                context["cases_referenced"].append(case)

        # Track statute references
        statute_pattern = r'(?:section|article|act|chapter)\s+\d+'
        statutes = re.findall(statute_pattern, content)
        for stat in statutes:
            if stat not in context["statutes_referenced"]:
                context["statutes_referenced"].append(stat)

        # Track question types
        if any(q in content for q in ["what is", "define", "explain"]):
            if "definition" not in context["question_types"]:
                context["question_types"].append("definition")
        if any(q in content for q in ["how does", "how do", "process"]):
            if "process" not in context["question_types"]:
                context["question_types"].append("process")
        if any(q in content for q in ["case", "precedent", "ruling"]):
            if "case_analysis" not in context["question_types"]:
                context["question_types"].append("case_analysis")

    return context


def get_session_summary(session: Dict[str, Any]) -> str:
    """Generate a one-line summary of what the session covered."""
    context = session.get("context", {})
    topics = context.get("topics_discussed", [])
    queries = len(context.get("search_queries", []))
    messages = len(session.get("messages", []))

    if topics:
        return f"Discussed {', '.join(topics[:3])} ({messages} messages, {queries} searches)"
    return f"{messages} messages in session"
