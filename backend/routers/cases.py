from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.database import async_session, Case
from models.schemas import CaseResponse, CaseComparisonRequest, CaseComparisonResponse
from services.scraper import search_cases as scrape_search_cases
from services.ai_service import compare_cases as ai_compare_cases, generate_case_summary, generate_citation
import logging
import uuid

logger = logging.getLogger("juriscore")
router = APIRouter()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


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
    try:
        external_cases = await scrape_search_cases(
            q, filters={"court": court, "year_from": year_from, "year_to": year_to, "subject": subject}
        )
        results: List[CaseResponse] = []
        for c in external_cases:
            case = Case(
                id=str(uuid.uuid4()),
                title=c.get("title", ""),
                citation=c.get("citation", ""),
                court=c.get("court", ""),
                year=int(c.get("year", 0)) if c.get("year") else 0,
                subject_tags=c.get("subject_tags"),
                full_text=c.get("full_text", ""),
                judges=c.get("judges"),
            )
            session.add(case)
            await session.flush()
            results.append(CaseResponse(
                id=case.id,
                title=case.title,
                citation=case.citation,
                court=case.court,
                year=case.year,
                subject_tags=case.subject_tags,
                judges=case.judges,
                created_at=case.created_at,
            ))
        await session.commit()
        return results
    except Exception as e:
        logger.error(f"search_cases error: {e}")
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")


@router.get("/recent", response_model=List[CaseResponse])
async def get_recent_cases(limit: int = 10, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Case).order_by(Case.created_at.desc()).limit(limit)
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


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        id=case.id, title=case.title, citation=case.citation, court=case.court,
        year=case.year, subject_tags=case.subject_tags, summary=case.summary,
        ratio=case.ratio, judges=case.judges, created_at=case.created_at,
    )


@router.get("/{case_id}/summary", response_model=Dict[str, Any])
async def get_case_summary(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.summary:
        return case.summary
    summary = generate_case_summary(case.full_text)
    case.summary = summary
    case.updated_at = datetime.utcnow()
    await session.commit()
    return summary


@router.post("/{case_id}/save")
async def save_case(case_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"status": "saved", "case_id": case_id}


@router.post("/compare", response_model=CaseComparisonResponse)
async def compare_cases(request: CaseComparisonRequest, session: AsyncSession = Depends(get_session)):
    result_a = await session.execute(select(Case).where(Case.id == request.case_a_id))
    result_b = await session.execute(select(Case).where(Case.id == request.case_b_id))
    case_a = result_a.scalar_one_or_none()
    case_b = result_b.scalar_one_or_none()
    if not case_a or not case_b:
        raise HTTPException(status_code=404, detail="Case not found")
    comparison = ai_compare_cases(case_a.full_text, case_b.full_text)
    return CaseComparisonResponse(comparison=comparison)


@router.get("/citations/generate")
async def get_citation(url: str):
    citation_data = generate_citation({"url": url})
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
