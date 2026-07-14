from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
from services.scraper import search_all, search_kenyalaw
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.get("")
async def universal_search(
    q: Optional[str] = Query(None, description="Search query"),
    doc_type: Optional[str] = Query(None, description="Document type: judgment, legislation, gazette, bill, all"),
    court: Optional[str] = Query(None, description="Court name filter"),
    date_from: Optional[str] = Query(None, description="Date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Date to (YYYY-MM-DD)"),
    page: int = Query(1, ge=1),
    ordering: Optional[str] = Query("-score", description="Sort: -score, -date, date"),
    limit: int = Query(20, le=100),
):
    if not q:
        return {"count": 0, "results": [], "facets": {}}

    filters = {
        "doc_type": doc_type,
        "court": court,
        "date_from": date_from,
        "date_to": date_to,
        "page": page,
        "ordering": ordering,
        "limit": limit,
    }
    return await search_all(q, filters)


@router.get("/courts")
async def list_courts(q: Optional[str] = Query(None)):
    data = await search_kenyalaw(query=q or "a", limit=0)
    courts = data.get("facets", {}).get("courts", [])
    return courts


@router.get("/types")
async def list_doc_types(q: Optional[str] = Query(None)):
    data = await search_kenyalaw(query=q or "a", limit=0)
    doc_types = data.get("facets", {}).get("doc_types", [])
    return doc_types
