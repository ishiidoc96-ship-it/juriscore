from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from api.backend.services.scraper import search_all, search_kenyalaw
from api.backend.services.brain import (
    brain_search, brain_get_case, brain_get_related_cases,
    brain_get_statutes, brain_get_all_courts, brain_get_all_doc_types,
    brain_stats, load_brain,
)
from api.backend.services.africa_law_scraper import search_africanlii, search_african_court, get_african_jurisdictions, get_african_courts
from api.backend.services.world_law_scraper import search_worldlii, search_global_case_law, get_world_jurisdictions, get_world_sources, get_legal_systems
from api.backend.services.local_db import search_local_db, get_db_stats
from api.backend.services.ai_orchestrator import ai_reason_and_search, ai_legal_concept, ai_case_analysis
from api.backend.services.ai_service import (
    generate_summary_from_metadata, legal_research_assistant,
    format_citation, explain_legal_concept, compare_jurisdictions,
    generate_legal_memo, analyze_case_law, interpret_statute,
    generate_study_plan, translate_legal_term,
)
import asyncio
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()

# Try to load brain at startup
try:
    load_brain()
except Exception as e:
    logger.warning(f"Brain data not loaded: {e}")


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
    jurisdiction: Optional[str] = Query("kenya"),
    country: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    legal_system: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    ordering: Optional[str] = Query("-score"),
    limit: int = Query(50, le=100),
):
    """Universal search across Kenya, Africa, and World legal sources."""
    if not q:
        return {"count": 0, "results": [], "facets": {}}

    jurisdiction = jurisdiction.lower().strip()

    # Kenya Law search — universal across all document types
    if jurisdiction == "kenya" or jurisdiction == "ke":
        all_results = []
        sources_used = []

        # Layer 1a: Vector search (semantic + keyword hybrid via zvec)
        try:
            from api.backend.services.vector_search import vector_search as zvec_search
            vec_results = zvec_search(q, doc_type=doc_type, court=court, top_k=limit)
            if vec_results:
                for r in vec_results:
                    r["source"] = "vector_search"
                all_results.extend(vec_results)
                sources_used.append("vector_search")
                logger.info(f"Vector search returned {len(vec_results)} results for '{q}'")
        except Exception as e:
            logger.debug(f"Vector search unavailable: {e}")

        # Layer 1b: KenyaLaw crawled database (instant, full-text search of downloaded content)
        try:
            from api.backend.services.kenyalaw_local_db import search_local
            crawled = await search_local(q, doc_type=doc_type, court=court, limit=limit)
            if crawled.get("count", 0) > 0:
                for r in crawled["results"]:
                    r["source"] = "crawled_db"
                all_results.extend(crawled["results"])
                sources_used.append("crawled_db")
                logger.info(f"Crawled DB returned {crawled['count']} results for '{q}'")
        except Exception as e:
            logger.debug(f"Crawled DB search failed (not initialized yet): {e}")

        # Layer 1b: Local JSON database (instant, brain data)
        local_results = search_local_db(q, doc_type=doc_type, court=court, limit=limit)
        if local_results:
            for r in local_results:
                r["source"] = "local_db"
            all_results.extend(local_results)
            sources_used.append("local_db")
            logger.info(f"Local DB returned {len(local_results)} results for '{q}'")

        # Layer 2: Brain search (instant, searches ALL types: cases, legislation, gazettes, bills, articles)
        brain_result = brain_search(q, doc_type=doc_type, court=court, limit=limit)
        if brain_result.get("count", 0) > 0:
            for r in brain_result.get("results", []):
                r["source"] = "brain"
            all_results.extend(brain_result.get("results", []))
            sources_used.append("brain")
            logger.info(f"Brain returned {brain_result['count']} results for '{q}'")

        # Layer 3: Live KenyaLaw.org search (additional results from web)
        try:
            kenya_results = await search_kenyalaw(query=q, limit=limit)
            if kenya_results.get("results"):
                for r in kenya_results["results"]:
                    r["source"] = "kenyalaw"
                all_results.extend(kenya_results["results"])
                sources_used.append("kenyalaw")
        except Exception as e:
            logger.warning(f"KenyaLaw search failed: {e}")

        # Deduplicate by title
        seen_titles = set()
        unique_results = []
        for r in all_results:
            t = r.get("title", "")
            if t and t not in seen_titles:
                seen_titles.add(t)
                unique_results.append(r)

        results = unique_results[:limit]
        logger.info(f"Universal Kenya search: {len(results)} results from {sources_used}")

        return {
            "count": len(results),
            "results": results,
            "jurisdiction": "kenya",
            "source": "universal",
            "sources_used": sources_used,
        }

    # Africa Law search
    elif jurisdiction == "africa" or jurisdiction == "af":
        try:
            result = await search_africanlii(
                query=q,
                doc_type=doc_type,
                country=country,
                page=page,
                limit=limit,
            )
            # Also search African regional courts
            court_results = await search_african_court(
                query=q,
                court=court,
                limit=limit // 2,
            )
            # Merge results
            all_results = result.get("results", []) + court_results.get("results", [])
            result["results"] = all_results[:limit]
            result["count"] = len(all_results)
            result["jurisdiction"] = "africa"
            return result
        except Exception as e:
            logger.error(f"Africa search failed: {e}")
            return {"count": 0, "results": [], "facets": {}, "jurisdiction": "africa", "error": str(e)}

    # World Law search
    elif jurisdiction == "world" or jurisdiction == "ww":
        try:
            result = await search_worldlii(
                query=q,
                doc_type=doc_type,
                jurisdiction=country,
                source=source,
                page=page,
                limit=limit,
            )
            # Also search global case law
            global_results = await search_global_case_law(
                query=q,
                legal_system=legal_system,
                country=country,
                limit=limit // 2,
            )
            # Merge results
            all_results = result.get("results", []) + global_results.get("results", [])
            result["results"] = all_results[:limit]
            result["count"] = len(all_results)
            result["jurisdiction"] = "world"
            return result
        except Exception as e:
            logger.error(f"World search failed: {e}")
            return {"count": 0, "results": [], "facets": {}, "jurisdiction": "world", "error": str(e)}

    # Default: AI-First Search with comprehensive results
    else:
        return await ai_reason_and_search(
            query=q,
            doc_type=doc_type,
            court=court,
            jurisdiction=jurisdiction,
            limit=limit,
        )


@router.get("/jurisdictions")
async def list_jurisdictions():
    """List all available jurisdictions."""
    return {
        "kenya": {
            "name": "Kenya",
            "id": "kenya",
            "sources": ["KenyaLaw.org"],
            "courts": ["Supreme Court", "Court of Appeal", "High Court", "Environment and Land Court", "Employment and Labour Relations Court"],
        },
        "africa": {
            "name": "Africa",
            "id": "africa",
            "sources": ["AfricanLII", "ECOWAS Court", "East African Court of Justice", "SADC Tribunal"],
            "courts": get_african_courts(),
            "jurisdictions": get_african_jurisdictions(),
        },
        "world": {
            "name": "World",
            "id": "world",
            "sources": [s["name"] for s in get_world_sources()],
            "legal_systems": get_legal_systems(),
            "jurisdictions": get_world_jurisdictions(),
        },
    }


@router.post("/summarize")
async def summarize_document(req: SummarizeRequest):
    """Generate a human-readable summary of a document from its metadata."""
    try:
        summary = await generate_summary_from_metadata(
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
async def list_courts(q: Optional[str] = Query(None), jurisdiction: Optional[str] = Query("kenya")):
    """List courts for a jurisdiction."""
    jurisdiction = jurisdiction.lower().strip()

    if jurisdiction == "africa" or jurisdiction == "af":
        courts = get_african_courts()
        return [{"key": c, "count": 0} for c in courts]

    elif jurisdiction == "world" or jurisdiction == "ww":
        jurisdictions = get_world_jurisdictions()
        all_courts = []
        for j in jurisdictions:
            for c in j.get("courts", []):
                all_courts.append({"key": c, "count": 0, "country": j["name"]})
        return all_courts

    else:
        # Try live KenyaLaw first
        try:
            data = await search_kenyalaw(query=q or "a", limit=0)
            courts = data.get("facets", {}).get("courts", [])
            if courts:
                return courts
        except Exception as e:
            logger.warning(f"Live courts fetch failed: {e}")

        # Fallback to brain data
        brain_courts = brain_get_all_courts()
        return [{"key": c, "count": 0} for c in brain_courts]


@router.get("/types")
async def list_doc_types(q: Optional[str] = Query(None), jurisdiction: Optional[str] = Query("kenya")):
    """List document types for a jurisdiction."""
    jurisdiction = jurisdiction.lower().strip()

    if jurisdiction == "africa" or jurisdiction == "af":
        return [
            {"key": "judgment", "count": 0},
            {"key": "legislation", "count": 0},
            {"key": "treaty", "count": 0},
            {"key": "regulation", "count": 0},
        ]

    elif jurisdiction == "world" or jurisdiction == "ww":
        return [
            {"key": "case", "count": 0},
            {"key": "legislation", "count": 0},
            {"key": "regulation", "count": 0},
            {"key": "journal", "count": 0},
            {"key": "treaty", "count": 0},
        ]

    else:
        # Try live KenyaLaw first
        try:
            data = await search_kenyalaw(query=q or "a", limit=0)
            doc_types = data.get("facets", {}).get("doc_types", [])
            if doc_types:
                return doc_types
        except Exception as e:
            logger.warning(f"Live doc types fetch failed: {e}")

        # Fallback to brain data
        return brain_get_all_doc_types()


@router.get("/rewrite")
async def rewrite_query(q: str = Query(...)):
    """AI-powered query rewriting: fix misspellings, expand terms."""
    from api.backend.services.ai_service import rewrite_search_query
    result = await rewrite_search_query(q)
    return result


# ==================== AI TOOLS ENDPOINTS ====================

class LegalResearchRequest(BaseModel):
    query: str
    jurisdiction: str = "kenya"


class CitationRequest(BaseModel):
    case_data: Dict[str, Any]
    jurisdiction: str = "kenya"


class ConceptRequest(BaseModel):
    concept: str
    jurisdiction: str = "kenya"


class JurisdictionCompareRequest(BaseModel):
    legal_issue: str
    jurisdictions: List[str] = ["kenya", "nigeria", "south_africa", "uk", "us"]


class LegalMemoRequest(BaseModel):
    issue: str
    facts: str = ""
    jurisdiction: str = "kenya"


class StatuteInterpretRequest(BaseModel):
    statute_text: str
    section: str = ""
    jurisdiction: str = "kenya"


class StudyPlanRequest(BaseModel):
    topic: str
    exam_date: str = ""
    jurisdiction: str = "kenya"


class TranslationRequest(BaseModel):
    term: str
    source_lang: str = "english"
    target_lang: str = "swahili"
    jurisdiction: str = "kenya"


@router.post("/tools/research")
async def ai_legal_research(req: LegalResearchRequest):
    """Comprehensive legal research across jurisdictions."""
    try:
        result = await legal_research_assistant(req.query, req.jurisdiction)
        return result
    except Exception as e:
        logger.error(f"Legal research failed: {e}")
        raise HTTPException(status_code=500, detail="Research temporarily unavailable")


@router.post("/tools/citation")
async def ai_format_citation(req: CitationRequest):
    """Format citation according to jurisdiction rules."""
    try:
        result = await format_citation(req.case_data, req.jurisdiction)
        return {"citation": result}
    except Exception as e:
        logger.error(f"Citation formatting failed: {e}")
        raise HTTPException(status_code=500, detail="Citation formatting unavailable")


@router.post("/tools/explain")
async def ai_explain_concept(req: ConceptRequest):
    """Explain a legal concept with jurisdiction context."""
    try:
        result = await explain_legal_concept(req.concept, req.jurisdiction)
        return {"explanation": result}
    except Exception as e:
        logger.error(f"Concept explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Explanation unavailable")


@router.post("/tools/compare-jurisdictions")
async def ai_compare_jurisdictions(req: JurisdictionCompareRequest):
    """Compare legal issues across jurisdictions."""
    try:
        result = await compare_jurisdictions(req.legal_issue, req.jurisdictions)
        return result
    except Exception as e:
        logger.error(f"Jurisdiction comparison failed: {e}")
        raise HTTPException(status_code=500, detail="Comparison unavailable")


@router.post("/tools/legal-memo")
async def ai_legal_memo(req: LegalMemoRequest):
    """Generate a legal memorandum."""
    try:
        result = await generate_legal_memo(req.issue, req.facts, req.jurisdiction)
        return {"memo": result}
    except Exception as e:
        logger.error(f"Legal memo generation failed: {e}")
        raise HTTPException(status_code=500, detail="Memo generation unavailable")


@router.post("/tools/analyze-case")
async def ai_analyze_case(req: LegalResearchRequest):
    """Deep analysis of case law."""
    try:
        result = await analyze_case_law(req.query, req.jurisdiction)
        return result
    except Exception as e:
        logger.error(f"Case analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Case analysis unavailable")


@router.post("/tools/interpret-statute")
async def ai_interpret_statute(req: StatuteInterpretRequest):
    """Interpret a statute with case law context."""
    try:
        result = await interpret_statute(req.statute_text, req.section, req.jurisdiction)
        return result
    except Exception as e:
        logger.error(f"Statute interpretation failed: {e}")
        raise HTTPException(status_code=500, detail="Statute interpretation unavailable")


@router.post("/tools/study-plan")
async def ai_study_plan(req: StudyPlanRequest):
    """Generate a study plan for a legal topic."""
    try:
        result = await generate_study_plan(req.topic, req.exam_date, req.jurisdiction)
        return result
    except Exception as e:
        logger.error(f"Study plan generation failed: {e}")
        raise HTTPException(status_code=500, detail="Study plan unavailable")


@router.post("/tools/translate")
async def ai_translate_term(req: TranslationRequest):
    """Translate legal terms with context."""
    try:
        result = await translate_legal_term(req.term, req.source_lang, req.target_lang, req.jurisdiction)
        return result
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise HTTPException(status_code=500, detail="Translation unavailable")


# ---------- Search History ----------

class SearchHistoryRequest(BaseModel):
    user_id: str
    query: str
    jurisdiction: str = "kenya"
    doc_type: str = ""
    results_count: int = 0


@router.post("/history")
async def save_search_history(req: SearchHistoryRequest):
    """Save a search query to the user's history."""
    from api.backend.models.database import async_session, SearchHistory
    from sqlalchemy import select
    try:
        async with async_session() as session:
            entry = SearchHistory(
                user_id=req.user_id,
                query=req.query,
                jurisdiction=req.jurisdiction,
                doc_type=req.doc_type or None,
                results_count=req.results_count,
            )
            session.add(entry)
            await session.commit()
            return {"status": "saved"}
    except Exception as e:
        logger.error(f"Failed to save search history: {e}")
        return {"status": "error"}


@router.get("/history")
async def get_search_history(user_id: str = Query(...), limit: int = Query(10)):
    """Get the user's recent search history, deduplicated by query."""
    from api.backend.models.database import async_session, SearchHistory
    from sqlalchemy import select, desc
    try:
        async with async_session() as session:
            result = await session.execute(
                select(SearchHistory)
                .where(SearchHistory.user_id == user_id)
                .order_by(desc(SearchHistory.created_at))
                .limit(limit * 3)
            )
            rows = result.scalars().all()
            seen = set()
            history = []
            for r in rows:
                key = r.query.strip().lower()
                if key not in seen:
                    seen.add(key)
                    history.append({
                        "id": r.id,
                        "query": r.query,
                        "jurisdiction": r.jurisdiction,
                        "doc_type": r.doc_type,
                        "results_count": r.results_count,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    })
                if len(history) >= limit:
                    break
            return history
    except Exception as e:
        logger.error(f"Failed to get search history: {e}")
        return []


@router.delete("/history/{entry_id}")
async def delete_search_history(entry_id: str):
    """Delete a single search history entry."""
    from api.backend.models.database import async_session, SearchHistory
    from sqlalchemy import delete
    try:
        async with async_session() as session:
            await session.execute(delete(SearchHistory).where(SearchHistory.id == entry_id))
            await session.commit()
            return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Failed to delete search history: {e}")
        return {"status": "error"}


@router.delete("/history")
async def clear_search_history(user_id: str = Query(...)):
    """Clear all search history for a user."""
    from api.backend.models.database import async_session, SearchHistory
    from sqlalchemy import delete
    try:
        async with async_session() as session:
            await session.execute(delete(SearchHistory).where(SearchHistory.user_id == user_id))
            await session.commit()
            return {"status": "cleared"}
    except Exception as e:
        logger.error(f"Failed to clear search history: {e}")


# ---------- Local Database Sync ----------

@router.get("/stats")
async def search_stats():
    """Return search statistics including local database status."""
    try:
        total = await _get_total_count()
        stats = {"total_documents": total, "services": ["kenyalaw", "africanlii", "worldlii"]}

        try:
            from api.backend.services.kenyalaw_local_db import get_database_stats, get_sync_status
            local_stats = await get_database_stats()
            sync_status = await get_sync_status()
            stats["local_database"] = local_stats
            if sync_status:
                stats["last_sync"] = sync_status
        except Exception as e:
            stats["local_database"] = {"error": str(e)}

        return {"status": "healthy", **stats, "last_updated": "live"}
    except Exception as e:
        logger.error(f"Stats check failed: {e}")
        return {"status": "degraded", "error": str(e)}


@router.post("/sync")
async def sync_local_database():
    """Sync live search results to local database for instant access."""
    from api.backend.services.kenyalaw_local_db import get_database_stats, update_sync_status
    from api.backend.services.scraper import search_kenyalaw

    await update_sync_status(status="syncing")

    try:
        popular_queries = [
            "constitutional law", "criminal law", "contract law",
            "employment law", "family law", "land law", "tax law",
            "judicial review", "human rights", "election law",
            "marriage", "divorce", "custody", "inheritance",
            "murder", "theft", "fraud", "corruption",
            "Nairobi", "Mombasa", "Kisumu", "Nakuru",
            "Supreme Court", "High Court", "Court of Appeal",
        ]

        total_synced = 0
        for query in popular_queries:
            try:
                data = await search_kenyalaw(query=query, limit=50)
                if data.get("results"):
                    from api.backend.services.kenyalaw_local_db import sync_live_results_to_db
                    await sync_live_results_to_db(data["results"])
                    total_synced += len(data["results"])
            except Exception as e:
                logger.warning(f"Failed to sync query '{query}': {e}")

        stats = await get_database_stats()
        await update_sync_status(
            total_cases=stats["total_cases"],
            total_legislation=stats["total_legislation"],
            total_articles=stats["total_articles"],
            status="idle"
        )

        return {
            "status": "completed",
            "total_synced": total_synced,
            "database_stats": stats,
        }
    except Exception as e:
        await update_sync_status(status="error", error_message=str(e))
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")


@router.post("/sync/full")
async def start_full_crawl():
    """Start full KenyaLaw.org site crawl in background.
    Downloads every document: judgments, legislation, articles, bills, etc."""
    from api.backend.services.kenyalaw_crawler import start_full_crawl
    result = await start_full_crawl()
    return result


@router.post("/sync/stop")
async def stop_crawl():
    """Stop the site crawl."""
    from api.backend.services.kenyalaw_crawler import stop_crawl
    result = await stop_crawl()
    return result


@router.get("/sync/progress")
async def crawl_progress():
    """Get crawl progress, statistics, and completion notification."""
    from api.backend.services.kenyalaw_crawler import get_crawl_progress
    return await get_crawl_progress()


@router.post("/sync/clear")
async def clear_crawl_state():
    """Clear all crawl progress for a fresh start."""
    from api.backend.services.kenyalaw_crawler import clear_crawl_state
    return await clear_crawl_state()


@router.get("/sync/notify")
async def check_notification():
    """Check if the crawl has completed (for frontend polling)."""
    from api.backend.services.kenyalaw_crawler import NOTIFICATION_FILE
    import json as _json
    if NOTIFICATION_FILE.exists():
        try:
            return _json.loads(NOTIFICATION_FILE.read_text())
        except Exception:
            pass
    return {"status": "none", "message": "No notifications"}


@router.get("/daily-updates")
async def get_daily_updates(
    court: Optional[str] = Query(None),
    limit: int = Query(30, le=50),
):
    """Get recently added/updated cases from KenyaLaw.org, organized by court."""
    from api.backend.services.scraper import scrape_daily_updates

    results = []
    try:
        results = await scrape_daily_updates(court=court, limit=limit)
    except Exception as e:
        logger.warning(f"Live daily updates failed, using brain data: {e}")

    # Fallback to brain data if no live results
    if not results:
        brain = brain_search(court or "", doc_type="case", limit=limit)
        results = brain.get("results", [])
        logger.info(f"Brain daily updates returned {len(results)} results")

    # Group by court
    by_court = {}
    for r in results:
        c = r.get("court") or "Other"
        if c not in by_court:
            by_court[c] = []
        by_court[c].append(r)

    return {
        "count": len(results),
        "results": results,
        "courts": list(by_court.keys()),
        "by_court": by_court,
    }


@router.get("/brain/stats")
async def get_brain_stats():
    """Get brain data statistics."""
    brain = brain_stats()
    local_db = get_db_stats()
    return {
        "brain": brain,
        "local_db": local_db,
    }


@router.get("/local-db/stats")
async def get_local_db_stats_endpoint():
    """Get local database statistics."""
    return get_db_stats()


# --- AI-Powered Endpoints ---

@router.get("/concept")
async def explain_concept(q: str = Query(...)):
    """AI explains a legal concept with detailed analysis and citations."""
    return await ai_legal_concept(q)


@router.get("/case-analysis")
async def analyze_case(q: str = Query(...)):
    """AI provides comprehensive case analysis with facts, holdings, and significance."""
    return await ai_case_analysis(q)


@router.get("/ai-research")
async def ai_research(
    q: str = Query(...),
    doc_type: Optional[str] = Query(None),
    court: Optional[str] = Query(None),
    jurisdiction: str = Query("kenya"),
    limit: int = Query(20, le=50),
):
    """AI-first search: AI reasons about the query, decides what to fetch, returns detailed results."""
    return await ai_reason_and_search(
        query=q,
        doc_type=doc_type,
        court=court,
        jurisdiction=jurisdiction,
        limit=limit,
    )
