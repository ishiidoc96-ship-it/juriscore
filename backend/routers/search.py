from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from services.scraper import search_all, search_kenyalaw
from services.ai_service import generate_summary_from_metadata
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


class SummarizeRequest(BaseModel):
    title: str
    citation: str = ""
    court: str = ""
    date: str = ""
    doc_type: str = ""
    excerpt: str = ""
    url: str = ""


@router.get("")
async def universal_search(
    q: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    court: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    ordering: Optional[str] = Query("-score"),
    limit: int = Query(50, le=100),
):
    if not q:
        return {"count": 0, "results": [], "facets": {}}

    filters = {
        "doc_type": doc_type,
        "court": court,
        "page": page,
        "ordering": ordering,
        "limit": limit,
    }
    return await search_all(q, filters)


@router.post("/summarize")
async def summarize_document(req: SummarizeRequest):
    """Generate a human-readable summary of a document from its metadata."""
    try:
        summary = generate_summary_from_metadata(
            title=req.title,
            citation=req.citation,
            court=req.court,
            date=req.date,
            doc_type=req.doc_type,
            excerpt=req.excerpt,
        )
        return {"summary": summary, "title": req.title}
    except Exception as e:
        logger.error(f"Summarize failed: {e}")
        raise HTTPException(status_code=500, detail="Summary generation failed")


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
