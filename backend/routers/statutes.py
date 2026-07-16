from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import Optional, List
from models.database import Statute
from models.schemas import StatuteResponse, StatuteSectionsQuery, StatuteSearchQuery
from services.scraper import scrape_statute
from core import get_session
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.get("/", response_model=List[StatuteResponse])
async def list_statutes(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Statute))
    statutes = result.scalars().all()
    return [
        StatuteResponse(
            id=s.id,
            title=s.title,
            citation=s.citation,
            cap_number=s.cap_number,
            amendments=s.amendments,
            created_at=s.created_at,
        )
        for s in statutes
    ]


@router.get("/search")
async def search_statutes(
    q: Optional[str] = Query(None),
    cap_number: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Statute)
    conditions = []
    if q:
        conditions.append(or_(Statute.title.ilike(f"%{q}%"), Statute.citation.ilike(f"%{q}%")))
    if cap_number:
        conditions.append(Statute.cap_number == cap_number)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    result = await session.execute(stmt)
    statutes = result.scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "citation": s.citation,
            "cap_number": s.cap_number,
        }
        for s in statutes
    ]


@router.get("/{statute_id}", response_model=StatuteResponse)
async def get_statute(statute_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Statute).where(Statute.id == statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=404, detail="Statute not found")
    return StatuteResponse(
        id=statute.id,
        title=statute.title,
        citation=statute.citation,
        cap_number=statute.cap_number,
        amendments=statute.amendments,
        created_at=statute.created_at,
    )


@router.get("/{statute_id}/sections")
async def get_statute_sections(
    statute_id: str,
    q: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Statute).where(Statute.id == statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=404, detail="Statute not found")
    full_text = statute.full_text
    if q:
        sections = [p.strip() for p in full_text.split("\n\n") if q.lower() in p.lower()]
        return {"statute_id": statute.id, "query": q, "sections": sections}
    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    return {"statute_id": statute.id, "sections": paragraphs}

