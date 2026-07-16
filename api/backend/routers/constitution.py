from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from api.backend.services.scraper import scrape_constitution
from api.backend.core import get_session
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


@router.get("/")
async def get_constitution(session: AsyncSession = Depends(get_session)):
    from api.backend.models.database import Statute
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
        return {"chapter_num": chapter_num, "title": "", "content": "Content unavailable."}
    full_text = data.get("full_text", "")
    lines = full_text.split("\n")
    capture = False
    chapter_lines = []
    chapter_title = ""
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith(f"CHAPTER {chapter_num}") or stripped.upper().startswith(f"CHAPTER {chapter_num} "):
            capture = True
            chapter_title = stripped
            continue
        if capture and stripped.upper().startswith("CHAPTER") and stripped != chapter_title:
            break
        if capture:
            chapter_lines.append(line)
    return {"chapter_num": chapter_num, "title": chapter_title, "content": "\n".join(chapter_lines) if chapter_lines else "Chapter not found."}


@router.get("/articles/{article_num}")
async def get_article(article_num: int):
    try:
        data = await scrape_constitution()
    except Exception as e:
        logger.error(f"Failed to scrape constitution: {e}")
        return {"article_num": article_num, "title": "", "content": "Content unavailable."}
    full_text = data.get("full_text", "")
    paragraphs = full_text.split("\n\n")
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if stripped.upper().startswith(f"ARTICLE {article_num}") or stripped.upper().startswith(f"ARTICLE {article_num} "):
            article_content = [stripped]
            for j in range(i + 1, len(paragraphs)):
                next_para = paragraphs[j].strip()
                if next_para.upper().startswith("ARTICLE "):
                    break
                article_content.append(next_para)
            return {"article_num": article_num, "title": stripped, "content": "\n\n".join(article_content)}
    return {"article_num": article_num, "title": "", "content": "Article not found."}


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
