from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date
from pydantic import BaseModel
from api.backend.models.database import SearchHistory
from api.backend.core import get_session
import logging
import uuid

logger = logging.getLogger("juriscore")
router = APIRouter()


# ── Pydantic models ──────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    id: str
    type: str
    title: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: str


class HistoryGroup(BaseModel):
    date: str
    label: str
    items: List[HistoryItem]


class RerunResponse(BaseModel):
    status: str
    query: str
    jurisdiction: str
    redirect_url: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _today() -> date:
    return date.today()


def _yesterday() -> date:
    return date.today() - timedelta(days=1)


def _days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


def _ts(d: date, hour: int = 12, minute: int = 0) -> str:
    return datetime(d.year, d.month, d.day, hour, minute).isoformat()


# ── Demo data ────────────────────────────────────────────────────────────────

DEMO_HISTORY: List[Dict[str, Any]] = [
    # Today
    {
        "id": "hist-001",
        "type": "search",
        "title": "Data Protection Act section 25 cross-border transfer",
        "metadata": {"query": "Data Protection Act s.25 cross-border transfer", "jurisdiction": "kenya", "doc_type": "case", "results_count": 14},
        "timestamp": _ts(_today(), 10, 30),
    },
    {
        "id": "hist-002",
        "type": "search",
        "title": "Constitutional limitation of rights Art. 24",
        "metadata": {"query": "Constitution Art. 24 limitation of rights", "jurisdiction": "kenya", "doc_type": "case", "results_count": 8},
        "timestamp": _ts(_today(), 11, 15),
    },
    {
        "id": "hist-003",
        "type": "search",
        "title": "Comparative GDPR adequacy decisions",
        "metadata": {"query": "GDPR adequacy decisions comparative law", "jurisdiction": "world", "doc_type": "legislation", "results_count": 22},
        "timestamp": _ts(_today(), 14, 0),
    },
    {
        "id": "hist-004",
        "type": "view",
        "title": "Republic v Cabinet Secretary, Ministry of Defence & Another",
        "metadata": {"case_id": "case-demo-001", "court": "High Court of Kenya at Nairobi", "year": 2022},
        "timestamp": _ts(_today(), 14, 45),
    },
    {
        "id": "hist-005",
        "type": "download",
        "title": "Written Submissions — Appellant.pdf",
        "metadata": {"file_name": "Written Submissions — Appellant.pdf", "file_size_bytes": 245760, "workspace_id": "ws-demo-001"},
        "timestamp": _ts(_today(), 15, 20),
    },
    # Yesterday
    {
        "id": "hist-006",
        "type": "search",
        "title": "Public interest litigation access to information Kenya",
        "metadata": {"query": "public interest litigation access to information Kenya", "jurisdiction": "kenya", "doc_type": "case", "results_count": 11},
        "timestamp": _ts(_yesterday(), 9, 0),
    },
    {
        "id": "hist-007",
        "type": "search",
        "title": "East African Court of Justice jurisdiction",
        "metadata": {"query": "East African Court of Justice jurisdiction", "jurisdiction": "africa", "doc_type": "case", "results_count": 7},
        "timestamp": _ts(_yesterday(), 16, 30),
    },
    {
        "id": "hist-008",
        "type": "view",
        "title": "Okiya Omtatah Okoiti v Attorney General",
        "metadata": {"case_id": "case-demo-002", "court": "High Court of Kenya at Milimani", "year": 2023},
        "timestamp": _ts(_yesterday(), 17, 10),
    },
    # 3 days ago
    {
        "id": "hist-009",
        "type": "search",
        "title": "Freedom of expression Art. 33 limitations",
        "metadata": {"query": "Constitution Art. 33 freedom of expression limitations", "jurisdiction": "kenya", "doc_type": "case", "results_count": 19},
        "timestamp": _ts(_days_ago(3), 13, 45),
    },
]


def _group_items(items: List[Dict[str, Any]], date_filter: Optional[str] = None) -> List[HistoryGroup]:
    """Group history items by date, optionally filtering by relative date label."""
    today = _today()
    yesterday = _yesterday()

    def _label(d: date) -> str:
        if d == today:
            return "Today"
        if d == yesterday:
            return "Yesterday"
        delta = (today - d).days
        return f"{delta} days ago"

    def _key(d: date) -> str:
        return d.isoformat()

    # Filter by relative date if requested
    if date_filter and date_filter != "all":
        target = None
        if date_filter == "today":
            target = today
        elif date_filter == "yesterday":
            target = yesterday
        if target is not None:
            items = [
                it for it in items
                if datetime.fromisoformat(it["timestamp"]).date() == target
            ]

    groups: Dict[str, HistoryGroup] = {}
    for item in items:
        d = datetime.fromisoformat(item["timestamp"]).date()
        k = _key(d)
        if k not in groups:
            groups[k] = HistoryGroup(date=k, label=_label(d), items=[])
        groups[k].items.append(
            HistoryItem(
                id=item["id"],
                type=item["type"],
                title=item["title"],
                metadata=item.get("metadata"),
                timestamp=item["timestamp"],
            )
        )

    return sorted(groups.values(), key=lambda g: g.date, reverse=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def list_history(
    date: Optional[str] = Query(None, description="Filter: today, yesterday, or all"),
    user_id: str = Query("demo-user", description="User ID"),
    session: AsyncSession = Depends(get_session),
):
    """
    List research history items grouped by date.

    Query params:
    - date=today | yesterday | all (default: all)
    - user_id: current user
    """
    # Try reading from DB first
    db_items: List[Dict[str, Any]] = []
    try:
        stmt = (
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .order_by(desc(SearchHistory.created_at))
            .limit(100)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
        for r in rows:
            # Map SearchHistory entries into the unified history item shape
            db_items.append({
                "id": r.id,
                "type": "search",
                "title": r.query,
                "metadata": {
                    "query": r.query,
                    "jurisdiction": r.jurisdiction,
                    "doc_type": r.doc_type,
                    "results_count": r.results_count,
                },
                "timestamp": r.created_at.isoformat() if r.created_at else datetime.utcnow().isoformat(),
            })
    except Exception as e:
        logger.warning(f"Failed to read search_history table: {e}")

    # Merge with demo data (DB entries first, then demo items not already present)
    all_items = list(db_items)
    seen_ids = {it["id"] for it in all_items}
    for demo in DEMO_HISTORY:
        if demo["id"] not in seen_ids:
            all_items.append(demo)

    groups = _group_items(all_items, date_filter=date)

    return {
        "user_id": user_id,
        "total_items": sum(len(g.items) for g in groups),
        "groups": [g.model_dump() for g in groups],
    }


@router.post("/search/{query_id}/rerun")
async def rerun_search(
    query_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Re-run a previous search by its history ID.

    Looks up the original query params from SearchHistory and returns
    a redirect URL that the frontend can navigate to.
    """
    # Try DB first
    try:
        stmt = select(SearchHistory).where(SearchHistory.id == query_id)
        result = await session.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry:
            params = []
            if entry.query:
                params.append(f"q={entry.query}")
            if entry.jurisdiction:
                params.append(f"jurisdiction={entry.jurisdiction}")
            if entry.doc_type:
                params.append(f"doc_type={entry.doc_type}")
            qs = "&".join(params)
            return RerunResponse(
                status="rerun",
                query=entry.query,
                jurisdiction=entry.jurisdiction,
                redirect_url=f"/search?{qs}",
            )
    except Exception as e:
        logger.warning(f"Failed to read search_history for rerun: {e}")

    # Fall back to demo data
    demo_entry = next((it for it in DEMO_HISTORY if it["id"] == query_id), None)
    if demo_entry and demo_entry["type"] == "search":
        meta = demo_entry.get("metadata", {})
        params = []
        if meta.get("query"):
            params.append(f"q={meta['query']}")
        if meta.get("jurisdiction"):
            params.append(f"jurisdiction={meta['jurisdiction']}")
        if meta.get("doc_type"):
            params.append(f"doc_type={meta['doc_type']}")
        qs = "&".join(params)
        return RerunResponse(
            status="rerun",
            query=meta.get("query", ""),
            jurisdiction=meta.get("jurisdiction", "kenya"),
            redirect_url=f"/search?{qs}",
        )

    raise HTTPException(status_code=404, detail="Search history entry not found")
