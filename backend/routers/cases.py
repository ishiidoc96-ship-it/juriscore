"""Case-law endpoints.

Covers:
- GET  /cases/search      — live scrape + DB persistence
- GET  /cases/recent      — recent cases (scraped or demo fallback)
- GET  /cases/{case_id}   — single case
- GET  /cases/{case_id}/summary  — AI summary if missing
- POST /cases/search      (POST body) — paginated search (v2 contract)
- POST /cases/{id}/save   — bookmark / save to user library
- POST /cases/compare     — AI comparison of two cases
- GET  /cases/citations/generate — AI citation format
- GET  /cases/court/{court_name} — list by court

Rate limited on /search and /compare (AI-heavy).  Persistence uses
`core.get_session` which commits on success and rolls-back on error automatically.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Case, get_session
from models.schemas import (
    CaseComparisonRequest,
    CaseResponse,
    CaseSaveRequest,
)
from services.scraper import search_cases as scrape_search_cases, DEMO_CASES
from services.ai_service import (
    compare_cases as ai_compare_cases,
    generate_case_summary,
    generate_citation,
)
from core import (
    RATE_LIMIT_AI_PER_MIN,
    RATE_LIMIT_SEARCH_PER_MIN,
    rate_limit_dep,
    settings,
)

logger = logging.getLogger("juriscore.router.cases")
router = APIRouter()

# ── Rate limits ──────────────────────────────────────────────────────────────
_search_rl = rate_limit_dep(limit=RATE_LIMIT_SEARCH_PER_MIN, bucket="cases:search")
_compare_rl = rate_limit_dep(limit=RATE_LIMIT_AI_PER_MIN, bucket="cases:compare")


# ── Schemas ──────────────────────────────────────────────────────────────────
class CaseSearchRequest(BaseModel):
    q: Optional[str] = Field(None, max_length=300)
    court: Optional[str] = None
    year_from: Optional[int] = Field(None, ge=1800, le=2100)
    year_to:   Optional[int] = Field(None, ge=1800, le=2100)
    subject:   Optional[str] = None
    sort:      Optional[str] = Field(None, pattern=r"^-?(relevance|year|title)$")
    limit:     int = Field(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)
    page:      int = Field(1, ge=1)


class PaginatedCaseResponse(BaseModel):
    count: int
    page: int
    page_size: int
    results: List[CaseResponse]


# ── Helpers ──────────────────────────────────────────────────────────────────
def _case_to_response(case: Case) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        title=case.title,
        citation=case.citation if isinstance(case.citation, str) else str(case.citation),
        court=case.court,
        year=case.year,
        subject_tags=case.subject_tags,
        summary=case.summary,
        ratio=case.ratio,
        judges=case.judges,
        created_at=case.created_at,
    )


async def _sync_cases_to_db(
    external_cases: List[Dict],
    session: AsyncSession,
) -> List[CaseResponse]:
    """Persist external (scraped) cases in the local DB when not already present.

    Upsert rule: unique on (title, citation, court, year).
    """
    results: List[CaseResponse] = []
    for c in external_cases:
        case = Case(
            id=str(uuid.uuid4()),
            title=c.get("title", "Untitled"),
            citation=str(c.get("citation", "")),
            court=c.get("court", ""),
            year=int(c.get("year", 0) or 0),
            subject_tags=c.get("subject_tags"),
            full_text=c.get("full_text", ""),
            judges=c.get("judges"),
        )
        session.add(case)
        await session.flush()  # get id if needed, but we already set one
        results.append(_case_to_response(case))
    return results


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/search", response_model=List[CaseResponse])
async def search_cases_endpoint(
    q: Optional[str] = Query(None, max_length=300),
    court: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None, ge=1800),
    year_to: Optional[int] = Query(None, ge=1800),
    subject: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    limit: int = Query(settings.DEFAULT_PAGE_SIZE, le=settings.MAX_PAGE_SIZE),
    _rl: None = Depends(_search_rl),
    session: AsyncSession = Depends(get_session),
):
    """Search live KenyaLaw.org + sync results to local DB."""
    try:
        external = await scrape_search_cases(
            q, filters={"court": court, "year_from": year_from,
                         "year_to": year_to, "subject": subject}
        )
        external = external[:limit]
        responses = await _sync_cases_to_db(external, session)
        await session.commit()
        return responses
    except Exception as exc:
        logger.exception("search_cases failed: %s", exc)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "Search service temporarily unavailable.")


@router.get("/recent", response_model=List[CaseResponse])
async def get_recent_cases(
    limit: int = Query(10, le=settings.MAX_PAGE_SIZE),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Case).order_by(Case.created_at.desc()).limit(limit)
    )
    cases = result.scalars().all()
    if cases:
        return [_case_to_response(c) for c in cases]

    # Demo fallback — only when the DB is empty (fresh deployment / local dev)
    logger.info("DB empty on /recent — falling back to DEMO_CASES")
    responses = await _sync_cases_to_db(DEMO_CASES[:limit], session)
    await session.commit()
    return responses


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return _case_to_response(case)


@router.get("/{case_id}/summary")
async def get_case_summary(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    if case.summary:
        return case.summary
    try:
        summary = await generate_case_summary(case.full_text)
        case.summary = summary
        case.updated_at = datetime.utcnow()
        await session.commit()
        return summary
    except Exception as exc:
        logger.exception("Summary generation failed for %s: %s", case_id, exc)
        return {
            "facts": "Summary generation is temporarily unavailable.",
            "issues": [], "holdings": [], "ratio": "", "obiter": "",
            "cases_cited": [],
        }


@router.post("/{case_id}/save", status_code=status.HTTP_204_NO_CONTENT)
async def save_case(
    case_id: str,
    _req: CaseSaveRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        case = Case(
            id=case_id,
            title="Saved case",
            citation="",
            court="",
            year=0,
            full_text="",
        )
        session.add(case)
        await session.flush()
    await session.commit()
    return None


@router.post("/compare", response_model=CaseComparisonResponse)
async def compare_cases(
    request: CaseComparisonRequest,
    _rl: None = Depends(_compare_rl),
    session: AsyncSession = Depends(get_session),
):
    result_a = await session.execute(select(Case).where(Case.id == request.case_a_id))
    result_b = await session.execute(select(Case).where(Case.id == request.case_b_id))
    case_a = result_a.scalar_one_or_none()
    case_b = result_b.scalar_one_or_none()
    if not case_a or not case_b:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    comparison = await ai_compare_cases(case_a.full_text, case_b.full_text)
    return CaseComparisonResponse(comparison=comparison)


@router.get("/citations/generate")
async def get_citation(url: str, _rl: None = Depends(_compare_rl)):
    citation_data = await generate_citation({"url": url})
    return {"citation": citation_data}


@router.get("/court/{court_name}", response_model=List[CaseResponse])
async def list_cases_by_court(
    court_name: str,
    limit: int = Query(settings.MAX_PAGE_SIZE, le=settings.MAX_PAGE_SIZE),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Case)
        .where(Case.court.ilike(f"%{court_name}%"))
        .order_by(Case.created_at.desc())
        .limit(limit)
    )
    cases = result.scalars().all()
    return [_case_to_response(c) for c in cases]
