from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from models.database import async_session
from services.scraper import scrape_constitution
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


@router.get("/")
async def get_constitution(session: AsyncSession = Depends(get_session)):
    from models.database import Statute
    result = await session.execute(select(Statute).where(Statute.citation.ilike("%Constitution%")).limit(1))
    statute = result.scalar_one_or_none()
    if statute:
        return {"id": statute.id, "title": statute.title, "full_text": statute.full_text}
    try:
        data = await scrape_constitution()
        return data
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return {"title": "Constitution of Kenya 2010", "full_text": "Content unavailable. Please try again later."}


@router.get("/chapters", response_model=List[Dict])
async def get_chapters():
    try:
        data = await scrape_constitution()
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return []
    full_text = data.get("full_text", "")
    chunks: List[Dict] = []
    lines = full_text.split("\n")
    current: Dict = {"chapter": "", "title": "", "articles": []}
    for line in lines:
        line = line.strip()
        if line.upper().startswith("CHAPTER"):
            if current["chapter"]:
                chunks.append(current)
            current = {"chapter": line, "title": "", "articles": []}
        elif line:
            current["articles"].append(line)
    if current["chapter"]:
        chunks.append(current)
    return chunks


@router.get("/chapters/{chapter_num}")
async def get_chapter(chapter_num: int):
    try:
        data = await scrape_constitution()
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return {"chapter_num": chapter_num, "content": "Content unavailable."}
    return {"chapter_num": chapter_num, "content": data.get("full_text", "")}


@router.get("/articles/{article_num}")
async def get_article(article_num: int):
    try:
        data = await scrape_constitution()
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return {"article_num": article_num, "content": "Content unavailable."}
    return {"article_num": article_num, "content": data.get("full_text", "")}


@router.get("/search")
async def search_constitution(q: str = Query(...)):
    try:
        data = await scrape_constitution()
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return {"query": q, "results": []}
    text = data.get("full_text", "")
    paragraphs = [p for p in text.split("\n\n") if q.lower() in p.lower()]
    return {"query": q, "results": paragraphs}
