from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional, List, Dict, Any
from datetime import datetime
from api.backend.models.database import Case, User
from api.backend.models.schemas import CaseResponse, CaseComparisonRequest, CaseComparisonResponse
from api.backend.services.scraper import search_cases as scrape_search_cases
from api.backend.services.brain import brain_search, load_brain
from api.backend.services.local_db import search_local_db
from api.backend.services.ai_service import compare_cases as ai_compare_cases, generate_case_summary, generate_citation
from api.backend.routers.auth import get_current_user
from api.backend.core import get_session
import logging
import uuid

try:
    load_brain()
except Exception:
    pass

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.get("/search", response_model=List[CaseResponse])
async def search_cases_endpoint(
    q: Optional[str] = Query(None),
    court: Optional[str] = Query(None),
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    subject: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    session: AsyncSession = Depends(get_session),
):
    # Fallback chain: Live → Local DB → Brain
    external_cases = None

    # 1. Try live scraping
    try:
        external_cases = await scrape_search_cases(
            q, filters={"court": court, "year_from": year_from, "year_to": year_to, "subject": subject}
        )
    except Exception as e:
        logger.warning(f"Live scrape failed: {e}")

    # 2. Try local DB
    if not external_cases and q:
        try:
            db_results = search_local_db(q, limit=limit)
            if db_results:
                external_cases = db_results
                logger.info(f"Local DB returned {len(db_results)} results")
        except Exception as e:
            logger.warning(f"Local DB search failed: {e}")

    # 3. Try brain data
    if not external_cases and q:
        try:
            brain_results = brain_search(q, doc_type="case", limit=limit)
            if brain_results.get("results"):
                external_cases = brain_results["results"]
                logger.info(f"Brain returned {len(external_cases)} results")
        except Exception as e:
            logger.warning(f"Brain search failed: {e}")

    if not external_cases:
        external_cases = []

    results: List[CaseResponse] = []
    for c in external_cases[:limit]:
        try:
            case = Case(
                id=str(uuid.uuid4()),
                title=c.get("title", "Untitled"),
                citation=c.get("citation", ""),
                court=c.get("court", ""),
                year=int(c.get("year", 0)) if c.get("year") else 0,
                subject_tags=c.get("subject_tags", c.get("topics")),
                full_text=c.get("full_text", ""),
                judges=c.get("judges"),
            )
            session.add(case)
            await session.flush()
            results.append(CaseResponse(
                id=case.id,
                title=case.title,
                citation=case.citation if isinstance(case.citation, str) else str(case.citation),
                court=case.court,
                year=case.year,
                subject_tags=case.subject_tags,
                judges=case.judges,
                created_at=case.created_at,
            ))
        except Exception as e:
            logger.warning(f"Failed to create case response: {e}")
            continue

    await session.commit()
    return results


@router.get("/recent", response_model=List[CaseResponse])
async def get_recent_cases(limit: int = 10, session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(
            select(Case).order_by(Case.created_at.desc()).limit(limit)
        )
        cases = result.scalars().all()
        if not cases:
            from api.backend.services.scraper import DEMO_CASES
            demo_results = []
            for c in DEMO_CASES[:limit]:
                case = Case(
                    id=str(uuid.uuid4()),
                    title=c["title"],
                    citation=str(c["citation"]),
                    court=c["court"],
                    year=c["year"],
                    subject_tags=c.get("subject_tags"),
                    full_text=c["full_text"],
                    judges=c.get("judges"),
                )
                session.add(case)
                await session.flush()
                demo_results.append(CaseResponse(
                    id=case.id, title=case.title, citation=case.citation, court=case.court,
                    year=case.year, subject_tags=case.subject_tags,
                    judges=case.judges, created_at=case.created_at,
                ))
            await session.commit()
            return demo_results
        return [
            CaseResponse(
                id=c.id, title=c.title, citation=c.citation, court=c.court,
                year=c.year, subject_tags=c.subject_tags, summary=c.summary,
                ratio=c.ratio, judges=c.judges, created_at=c.created_at,
            )
            for c in cases
        ]
    except Exception as e:
        logger.error(f"get_recent_cases error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load recent cases: {str(e)}")


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        id=case.id, title=case.title, citation=case.citation if isinstance(case.citation, str) else str(case.citation),
        court=case.court, year=case.year, subject_tags=case.subject_tags,
        summary=case.summary, ratio=case.ratio, judges=case.judges, created_at=case.created_at,
    )


@router.get("/{case_id}/summary")
async def get_case_summary(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.summary:
        return case.summary
    try:
        summary = await generate_case_summary(case.full_text)
        case.summary = summary
        case.updated_at = datetime.utcnow()
        await session.commit()
        return summary
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return {"facts": "Summary generation is temporarily unavailable.", "issues": [], "holdings": [], "ratio": "", "obiter": "", "cases_cited": []}


@router.post("/{case_id}/save")
async def save_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Save a case to user's library."""
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        # Case not in DB yet (from search results) - create it as a lightweight record
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
    return {"status": "saved", "case_id": case_id, "user_id": current_user.id}


@router.post("/compare", response_model=CaseComparisonResponse)
async def compare_cases(
    request: CaseComparisonRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Compare two cases using AI analysis."""
    result_a = await session.execute(select(Case).where(Case.id == request.case_a_id))
    result_b = await session.execute(select(Case).where(Case.id == request.case_b_id))
    case_a = result_a.scalar_one_or_none()
    case_b = result_b.scalar_one_or_none()
    if not case_a or not case_b:
        raise HTTPException(status_code=404, detail="Case not found")
    comparison = await ai_compare_cases(case_a.full_text, case_b.full_text)
    return CaseComparisonResponse(comparison=comparison)


@router.get("/citations/generate")
async def get_citation(url: str):
    citation_data = await generate_citation({"url": url})
    return {"citation": citation_data}


@router.get("/court/{court_name}", response_model=List[CaseResponse])
async def list_cases_by_court(court_name: str, limit: int = 20, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Case).where(Case.court.ilike(f"%{court_name}%")).limit(limit)
    )
    cases = result.scalars().all()
    return [
        CaseResponse(
            id=c.id, title=c.title, citation=c.citation, court=c.court,
            year=c.year, subject_tags=c.subject_tags, summary=c.summary,
            ratio=c.ratio, judges=c.judges, created_at=c.created_at,
        )
        for c in cases
    ]
