"""
KenyaLaw Local Database Service
Downloads and caches KenyaLaw.org data for instant search
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from api.backend.core import get_session
from api.backend.models.database import (
    async_session, KenyaLawCase, KenyaLawLegislation,
    KenyaLawArticle, SearchCache, SyncStatus
)

logger = logging.getLogger("juriscore")

# Cache expiry: 24 hours for search results, 7 days for documents
SEARCH_CACHE_TTL_HOURS = 24
DOCUMENT_CACHE_TTL_DAYS = 7


def _hash_query(query: str, filters: Optional[Dict] = None) -> str:
    """Create a stable hash for a search query + filters."""
    key = query.lower().strip()
    if filters:
        key += json.dumps(filters, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:32]


async def get_sync_status() -> Optional[Dict]:
    """Get the current sync status."""
    async with async_session() as session:
        result = await session.execute(
            select(SyncStatus).order_by(SyncStatus.last_sync.desc()).limit(1)
        )
        status = result.scalar_one_or_none()
        if status:
            return {
                "last_sync": status.last_sync.isoformat(),
                "total_cases": status.total_cases,
                "total_legislation": status.total_legislation,
                "total_articles": status.total_articles,
                "status": status.status,
            }
    return None


async def update_sync_status(
    total_cases: int = 0,
    total_legislation: int = 0,
    total_articles: int = 0,
    status: str = "idle",
    error_message: Optional[str] = None,
):
    """Update sync status."""
    async with async_session() as session:
        result = await session.execute(
            select(SyncStatus).order_by(SyncStatus.last_sync.desc()).limit(1)
        )
        sync = result.scalar_one_or_none()
        if sync:
            sync.last_sync = datetime.utcnow()
            sync.total_cases = total_cases
            sync.total_legislation = total_legislation
            sync.total_articles = total_articles
            sync.status = status
            sync.error_message = error_message
        else:
            sync = SyncStatus(
                last_sync=datetime.utcnow(),
                total_cases=total_cases,
                total_legislation=total_legislation,
                total_articles=total_articles,
                status=status,
                error_message=error_message,
            )
            session.add(sync)
        await session.commit()


async def sync_live_results_to_db(results: List[Dict]):
    """Save live search results to local database for future instant access."""
    async with async_session() as session:
        for r in results:
            doc_type = r.get("doc_type", "judgment")
            doc_id = r.get("id", "")
            if not doc_id:
                continue

            if doc_type in ("judgment", "ruling", "decision", "case"):
                existing = await session.get(KenyaLawCase, doc_id)
                if not existing:
                    case = KenyaLawCase(
                        id=doc_id,
                        title=r.get("title", ""),
                        citation=r.get("citation", ""),
                        court=r.get("court", ""),
                        year=r.get("year", 0),
                        doc_type=doc_type,
                        excerpt=r.get("excerpt", ""),
                        url=r.get("url", ""),
                        search_url=r.get("search_url", r.get("url", "")),
                        topics=r.get("topics", []),
                        judges=r.get("judges", []),
                        case_number=r.get("case_number", ""),
                        full_text=r.get("full_text", ""),
                        score=r.get("score", 0.0),
                        last_synced=datetime.utcnow(),
                    )
                    session.add(case)
                else:
                    existing.last_synced = datetime.utcnow()
                    existing.score = r.get("score", existing.score)

            elif doc_type in ("legislation", "act", "statute", "regulation"):
                existing = await session.get(KenyaLawLegislation, doc_id)
                if not existing:
                    leg = KenyaLawLegislation(
                        id=doc_id,
                        title=r.get("title", ""),
                        citation=r.get("citation", ""),
                        act_number=r.get("case_number", ""),
                        year=r.get("year", 0),
                        doc_type=doc_type,
                        excerpt=r.get("excerpt", ""),
                        url=r.get("url", ""),
                        full_text=r.get("full_text", ""),
                        last_synced=datetime.utcnow(),
                    )
                    session.add(leg)

            elif doc_type in ("article", "law_report", "legal_news"):
                existing = await session.get(KenyaLawArticle, doc_id)
                if not existing:
                    article = KenyaLawArticle(
                        id=doc_id,
                        title=r.get("title", ""),
                        author=r.get("court", ""),
                        date=r.get("date", ""),
                        doc_type=doc_type,
                        excerpt=r.get("excerpt", ""),
                        url=r.get("url", ""),
                        full_text=r.get("full_text", ""),
                        last_synced=datetime.utcnow(),
                    )
                    session.add(article)

        await session.commit()
        logger.info(f"Synced {len(results)} results to local database")


async def search_local(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Search the local database for instant results."""
    query_lower = query.lower()
    query_words = set(query_lower.split())

    async with async_session() as session:
        results = []

        # Search cases
        if not doc_type or doc_type in ("judgment", "ruling", "decision", "case", "all"):
            stmt = select(KenyaLawCase)
            if court:
                stmt = stmt.where(KenyaLawCase.court.ilike(f"%{court}%"))
            result = await session.execute(stmt.limit(limit * 2))
            cases = result.scalars().all()

            for c in cases:
                score = 0
                title_lower = c.title.lower()
                excerpt_lower = (c.excerpt or "").lower()

                if query_lower in title_lower:
                    score += 100
                if all(w in title_lower for w in query_words):
                    score += 50
                for w in query_words:
                    if w in title_lower:
                        score += 10
                    elif w in excerpt_lower:
                        score += 5

                if score > 0:
                    results.append({
                        "id": c.id,
                        "doc_type": c.doc_type,
                        "title": c.title,
                        "citation": c.citation,
                        "court": c.court,
                        "year": c.year,
                        "excerpt": c.excerpt,
                        "url": c.url,
                        "topics": c.topics or [],
                        "judges": c.judges or [],
                        "score": score,
                        "source": "local_db",
                    })

        # Search legislation
        if not doc_type or doc_type in ("legislation", "act", "statute", "regulation", "all"):
            stmt = select(KenyaLawLegislation)
            result = await session.execute(stmt.limit(limit * 2))
            legs = result.scalars().all()

            for l in legs:
                score = 0
                title_lower = l.title.lower()

                if query_lower in title_lower:
                    score += 100
                if all(w in title_lower for w in query_words):
                    score += 50
                for w in query_words:
                    if w in title_lower:
                        score += 10

                if score > 0:
                    results.append({
                        "id": l.id,
                        "doc_type": l.doc_type,
                        "title": l.title,
                        "citation": l.citation,
                        "court": "",
                        "year": l.year,
                        "excerpt": l.excerpt,
                        "url": l.url,
                        "topics": [],
                        "score": score,
                        "source": "local_db",
                    })

        # Search articles
        if not doc_type or doc_type in ("article", "law_report", "legal_news", "all"):
            stmt = select(KenyaLawArticle)
            result = await session.execute(stmt.limit(limit * 2))
            articles = result.scalars().all()

            for a in articles:
                score = 0
                title_lower = a.title.lower()

                if query_lower in title_lower:
                    score += 100
                for w in query_words:
                    if w in title_lower:
                        score += 10

                if score > 0:
                    results.append({
                        "id": a.id,
                        "doc_type": a.doc_type,
                        "title": a.title,
                        "citation": "",
                        "court": a.author,
                        "year": 0,
                        "excerpt": a.excerpt,
                        "url": a.url,
                        "topics": [],
                        "score": score,
                        "source": "local_db",
                    })

        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:limit]

        return {
            "count": len(results),
            "results": results,
            "source": "local_database",
        }


async def get_cached_search(query: str, filters: Optional[Dict] = None) -> Optional[Dict]:
    """Get cached search results if available and not expired."""
    query_hash = _hash_query(query, filters)

    async with async_session() as session:
        result = await session.execute(
            select(SearchCache).where(
                and_(
                    SearchCache.query_hash == query_hash,
                    SearchCache.expires_at > datetime.utcnow()
                )
            )
        )
        cache = result.scalar_one_or_none()
        if cache:
            logger.info(f"Cache hit for query: {query[:50]}")
            return cache.results_json
    return None


async def cache_search_results(query: str, filters: Optional[Dict], results: Dict):
    """Cache search results for faster future access."""
    query_hash = _hash_query(query, filters)

    async with async_session() as session:
        # Remove old cache for this query
        await session.execute(
            text("DELETE FROM search_cache WHERE query_hash = :hash"),
            {"hash": query_hash}
        )

        cache = SearchCache(
            query_hash=query_hash,
            query_text=query,
            results_json=results,
            result_count=results.get("count", 0),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=SEARCH_CACHE_TTL_HOURS),
        )
        session.add(cache)
        await session.commit()


async def get_database_stats() -> Dict[str, int]:
    """Get counts of cached documents."""
    async with async_session() as session:
        cases = await session.execute(select(func.count(KenyaLawCase.id)))
        legs = await session.execute(select(func.count(KenyaLawLegislation.id)))
        articles = await session.execute(select(func.count(KenyaLawArticle.id)))
        cache = await session.execute(select(func.count(SearchCache.id)))

        return {
            "total_cases": cases.scalar(),
            "total_legislation": legs.scalar(),
            "total_articles": articles.scalar(),
            "cached_queries": cache.scalar(),
        }
