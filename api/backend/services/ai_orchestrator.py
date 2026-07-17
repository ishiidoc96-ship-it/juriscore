"""
AI-First Search Orchestrator

The AI REASONING LAYER that sits above all data sources.
It analyzes what the user wants, decides which tools to use,
and returns detailed, accurate results.

Flow: AI reasons → selects sources → fetches data → synthesizes response
"""
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")


async def ai_reason_and_search(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    jurisdiction: str = "kenya",
    limit: int = 20,
) -> Dict[str, Any]:
    """
    AI-first search: The AI reasons about the query, decides what sources
    to search, fetches data, and returns comprehensive results.
    """
    from api.backend.services.ai_service import _call_model
    from api.backend.services.brain import brain_search, brain_get_constitution, brain_get_all_courts
    from api.backend.services.local_db import search_local_db
    from api.backend.services.scraper import _search_kenyan_kb, search_kenyalaw

    # Step 1: AI analyzes the query
    analysis_prompt = f"""Analyze this legal research query and return a JSON object with:
- "intent": what the user is looking for (case_law, statute, constitution, legal_concept, court_info, recent_developments, general_research)
- "keywords": list of key search terms
- "courts_to_search": list of relevant courts to look in
- "doc_types": relevant document types
- "needs_full_text": boolean, does the user need full document text?
- "complexity": simple, moderate, or complex

Query: "{query}"
Doc type filter: {doc_type or "none"}
Court filter: {court or "none"}

Return ONLY the JSON object, no other text."""

    try:
        analysis_raw = await _call_model(analysis_prompt, max_tokens=500, temperature=0.2)
        # Clean up the response
        analysis_text = analysis_raw.strip()
        if analysis_text.startswith("```"):
            analysis_text = analysis_text.split("\n", 1)[1] if "\n" in analysis_text else analysis_text[3:]
            if analysis_text.endswith("```"):
                analysis_text = analysis_text[:-3]
            analysis_text = analysis_text.strip()
        analysis = json.loads(analysis_text)
    except Exception as e:
        logger.warning(f"AI analysis failed, using defaults: {e}")
        analysis = {
            "intent": "general_research",
            "keywords": query.split(),
            "courts_to_search": [court] if court else [],
            "doc_types": [doc_type] if doc_type else [],
            "needs_full_text": False,
            "complexity": "moderate",
        }

    intent = analysis.get("intent", "general_research")
    keywords = analysis.get("keywords", query.split())
    needs_full_text = analysis.get("needs_full_text", False)
    complexity = analysis.get("complexity", "moderate")

    # Step 2: Fetch from multiple sources
    all_results: List[Dict] = []

    # Always try local DB first (instant)
    db_results = search_local_db(query, doc_type=doc_type, court=court, limit=limit)
    if db_results:
        for r in db_results:
            r["source"] = "local_database"
        all_results.extend(db_results)

    # Try brain data
    try:
        brain_result = brain_search(query, doc_type=doc_type, court=court, limit=limit)
        if brain_result.get("results"):
            for r in brain_result["results"]:
                r["source"] = "brain"
            all_results.extend(brain_result["results"])
    except Exception as e:
        logger.warning(f"Brain search failed: {e}")

    # For constitution queries, get the full text
    if intent == "constitution" or "constitution" in query.lower():
        try:
            const = brain_get_constitution()
            if const:
                all_results.insert(0, {
                    "title": const.get("title", "Constitution of Kenya"),
                    "type": "constitution",
                    "source": "brain",
                    "year": 2010,
                    "excerpt": const.get("excerpt", ""),
                })
        except Exception:
            pass

    # For recent developments, try live scrape with timeout
    if intent == "recent_developments":
        try:
            import asyncio
            live = await asyncio.wait_for(
                search_kenyalaw(query=query, limit=limit),
                timeout=10,
            )
            if live.get("results"):
                for r in live["results"]:
                    r["source"] = "kenyalaw_live"
                all_results.extend(live["results"])
        except Exception as e:
            logger.warning(f"Live scrape for recent developments failed: {e}")

    # KB fallback if still empty
    if not all_results:
        kb = _search_kenyan_kb(query, limit=limit)
        for r in kb:
            r["source"] = "kenyan_kb"
        all_results.extend(kb)

    # Deduplicate by title
    seen_titles = set()
    unique_results = []
    for r in all_results:
        t = r.get("title", "")
        if t not in seen_titles:
            seen_titles.add(t)
            unique_results.append(r)
    all_results = unique_results[:limit]

    # Step 3: AI synthesizes comprehensive response
    results_json = json.dumps(all_results[:10], indent=2, default=str)

    synthesis_prompt = f"""You are a senior Kenyan legal researcher. Based on the search results below,
provide a DETAILED, COMPREHENSIVE, and ACCURATE response to the user's query.

QUERY: "{query}"
INTENT: {intent}
COMPLEXITY: {complexity}

SEARCH RESULTS:
{results_json}

INSTRUCTIONS:
- Provide a THOROUGH analysis - do NOT give short or vague answers
- If there are relevant cases, discuss their facts, holdings, and legal principles
- If there are relevant statutes, cite the specific sections and explain their application
- If the query is complex, break it down into sub-issues
- Always cite sources (title, citation, year)
- If results are limited, acknowledge what additional research might be needed
- Structure your response with clear headings and sections
- Be precise with legal terminology

Provide a detailed, well-structured response:"""

    try:
        ai_response = await _call_model(synthesis_prompt, max_tokens=2048, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI synthesis failed: {e}")
        ai_response = f"Found {len(all_results)} results for '{query}'. Results include cases, legislation, and legal resources from Kenyan legal databases."

    return {
        "count": len(all_results),
        "results": all_results,
        "ai_analysis": analysis,
        "ai_response": ai_response,
        "sources_used": list(set(r.get("source", "unknown") for r in all_results)),
        "query": query,
        "jurisdiction": jurisdiction,
    }


async def ai_legal_concept(query: str) -> Dict[str, Any]:
    """
    AI explains a legal concept with detailed analysis.
    """
    from api.backend.services.ai_service import _call_model
    from api.backend.services.brain import brain_search

    # Get related cases and statutes
    related = brain_search(query, limit=5)
    related_json = json.dumps(related.get("results", []), indent=2, default=str)

    prompt = f"""You are a senior Kenyan legal expert. Provide a COMPREHENSIVE explanation of the following legal concept:

CONCEPT: "{query}"

RELATED AUTHORITIES:
{related_json}

Provide a detailed explanation covering:
1. Definition and meaning in Kenyan law
2. Constitutional basis (if applicable)
3. Key legislation governing this area
4. Important cases that have shaped the law
5. Practical application in Kenya
6. Current developments or trends
7. Related concepts

Be thorough and detailed. Cite specific cases and statutes where possible."""

    try:
        response = await _call_model(prompt, max_tokens=2048, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI concept explanation failed: {e}")
        response = f"Legal concept: {query}. This is an important area of Kenyan law."

    return {
        "concept": query,
        "explanation": response,
        "related_cases": related.get("results", []),
    }


async def ai_case_analysis(case_title: str) -> Dict[str, Any]:
    """
    AI provides detailed analysis of a case.
    """
    from api.backend.services.ai_service import _call_model
    from api.backend.services.brain import brain_search

    # Search for the case
    case_results = brain_search(case_title, doc_type="case", limit=3)
    cases = case_results.get("results", [])
    cases_json = json.dumps(cases, indent=2, default=str)

    prompt = f"""You are a senior Kenyan legal analyst. Provide a COMPREHENSIVE analysis of this case:

CASE: "{case_title}"

CASE DATA:
{cases_json}

Provide a detailed analysis covering:
1. Case citation and court
2. Facts of the case
3. Legal issues presented
4. Arguments by parties
5. Court's decision/holding
6. Legal principles established
7. Significance and impact
8. How it relates to current law
9. Practical implications

Be thorough and detailed. This is for serious legal research."""

    try:
        response = await _call_model(prompt, max_tokens=2048, temperature=0.3)
    except Exception as e:
        logger.warning(f"AI case analysis failed: {e}")
        response = f"Case analysis for: {case_title}"

    return {
        "case": case_title,
        "analysis": response,
        "found_cases": cases,
    }
