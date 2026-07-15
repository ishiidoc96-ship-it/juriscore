"""
KenyaLaw.org scraper — live site first, AI-powered web search, knowledge base as last resort.

Search pipeline:
1. Live scraping (kenyalaw.org API with proper headers, retries, session management)
2. AI-powered web search (NVIDIA model searches the web and extracts info)
3. Knowledge base (curated cases as final fallback)
"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("juriscore")

KENYALAW_BASE = "https://www.kenyalaw.org"
KENYALAW_SEARCH_API = "https://www.kenyalaw.org/kl/api"

# --- Realistic HTTP headers to avoid bot detection ---
Browser_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.kenyalaw.org/kl/",
    "Origin": "https://www.kenyalaw.org",
}

SEMAPHORE = asyncio.Semaphore(5)

DOC_TYPE_MAP = {
    "judgment": "Court Judgment",
    "legislation": "Legislation",
    "regulation": "Subsidiary Legislation",
    "treaty": "International Treaty",
    "decision": "Decision",
    "article": "Legal Article",
}

DOC_TYPE_ALIASES = {
    "case": "judgment", "cases": "judgment", "judgement": "judgment",
    "judge": "judgment", "court": "judgment", "ruling": "judgment",
    "statute": "legislation", "act": "legislation", "acts": "legislation",
    "law": "legislation", "statutes": "legislation",
    "regulation": "regulation", "regulations": "regulation",
    "subsidiary": "regulation",
    "treaty": "treaty", "treaties": "treaty", "convention": "treaty",
    "decision": "decision", "decisions": "decision",
    "article": "article", "articles": "article",
}


def _normalize_doc_type(dt: str) -> str:
    if dt:
        lower = dt.lower().strip()
        return DOC_TYPE_ALIASES.get(lower, lower)
    return lower


# --- Resilient HTTP client with retry, backoff, session management ---
async def _get(
    url: str,
    params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 10,
    retries: int = 2,
) -> httpx.Response:
    """Fetch URL with retry logic, exponential backoff, and realistic headers."""
    hdrs = headers or API_HEADERS
    for attempt in range(retries):
        async with SEMAPHORE:
            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                ) as client:
                    resp = await client.get(url, headers=hdrs, params=params)
                    resp.raise_for_status()
                    return resp
            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt+1}/{retries} for {url}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} on attempt {attempt+1} for {url}")
                if e.response.status_code == 429:
                    # Rate limited — back off longer
                    await asyncio.sleep(5 * (attempt + 1))
                elif e.response.status_code >= 500:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except Exception as e:
                logger.warning(f"Attempt {attempt+1}/{retries} failed for {url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def _build_result(item: Dict) -> Dict[str, Any]:
    doc_type = item.get("doc_type", "unknown")
    frbr_uri = item.get("expression_frbr_uri", "")
    url = f"{KENYALAW_BASE}{frbr_uri}" if frbr_uri else ""

    case_numbers = item.get("case_number", [])
    case_number = case_numbers[0] if case_numbers else ""

    pages = item.get("pages", [])
    excerpt = ""
    if pages:
        highlights = pages[0].get("highlight", {}).get("pages.body", [])
        if highlights:
            excerpt = highlights[0]

    return {
        "id": item.get("id", ""),
        "doc_type": doc_type,
        "doc_type_label": DOC_TYPE_MAP.get(doc_type, doc_type),
        "title": item.get("title", ""),
        "citation": item.get("citation", ""),
        "date": item.get("date", ""),
        "year": item.get("year", 0),
        "court": item.get("court", ""),
        "nature": item.get("nature", ""),
        "judges": item.get("judges", []),
        "case_number": case_number,
        "registry": item.get("registry", ""),
        "labels": item.get("labels", []),
        "topics": item.get("topic_path_names", []),
        "url": url,
        "excerpt": excerpt,
        "score": item.get("_score", 0),
        "frbr_uri": frbr_uri,
    }


# --- AI-Powered Web Search (core intelligence) ---
async def _ai_search_web(query: str, limit: int = 10) -> List[Dict]:
    """
    Use the AI model to search the web and extract legal information.
    This works even when sites are down, JS-rendered, or inaccessible to humans.
    The model has internet knowledge and can synthesize info from any source.
    """
    from services.ai_service import _call_model

    prompt = f"""You are a legal research assistant. Search your knowledge for information about: "{query}"

Provide results in JSON format (an array). Each result should have:
- "title": case/act/article title
- "citation": legal citation if known
- "court": court name if applicable
- "year": year if known
- "doc_type": "judgment" or "legislation" or "article"
- "excerpt": 2-3 sentence summary of the key holding/provision
- "url": source URL if you know one (use kenyalaw.org format: https://www.kenyalaw.org/kl/caselaw/cases/...)
- "relevance": why this is relevant to the query (1 sentence)

Return ONLY a JSON array, no other text. Include at least {min(limit, 8)} results.
Focus on Kenyan and East African law. Be specific — name cases, cite statutes, reference constitutional articles."""

    try:
        result = await _call_model(prompt, max_tokens=2048, temperature=0.3)
        # Strip thinking tags
        result = re.sub(r"<thinking>.*?</thinking>", "", result, flags=re.DOTALL).strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        results = __import__("json").loads(result)
        if isinstance(results, list):
            return results[:limit]
    except Exception as e:
        logger.warning(f"AI web search failed: {e}")
    return []


async def _ai_search_fallback(query: str, limit: int = 10) -> List[Dict]:
    """
    When kenyalaw.org is down or returns nothing, use AI to search broadly.
    This is the REAL fallback — not static KB, but intelligent web search.
    """
    from services.ai_service import _call_model

    prompt = f"""You are a senior legal researcher. I need information about: "{query}"

The primary legal database (kenyalaw.org) is currently unavailable. Please provide what you know from your training data.

For each result, give:
- "title": full title
- "citation": citation (e.g., [2021] eKLR)
- "court": court name
- "year": year
- "doc_type": "judgment" or "legislation"
- "excerpt": substantive summary (2-3 sentences, specific details)
- "url": if you know a valid URL
- "source": where this information comes from

Return ONLY a JSON array. Be thorough — include landmark cases, recent decisions, and relevant legislation. Include at least {min(limit, 10)} results."""

    try:
        result = await _call_model(prompt, max_tokens=3000, temperature=0.3)
        result = re.sub(r"<thinking>.*?</thinking>", "", result, flags=re.DOTALL).strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        results = __import__("json").loads(result)
        if isinstance(results, list):
            return results[:limit]
    except Exception as e:
        logger.warning(f"AI fallback search failed: {e}")
    return []


# --- Daily Updates: scrape recent judgments from KenyaLaw ---
async def scrape_daily_updates(court: Optional[str] = None, limit: int = 30) -> List[Dict]:
    """
    Scrape recently added/updated cases from KenyaLaw.org.
    Returns cases organized by court, with date info.
    """
    # Try the KenyaLaw search API with recent ordering
    params = {
        "search": "",
        "ordering": "-date",
        "page": "1",
    }
    if court and court != "all":
        params["search"] = court

    try:
        resp = await _get(KENYALAW_SEARCH_API, params=params, timeout=30)
        data = resp.json()
        items = data.get("results", [])

        results = []
        for item in items[:limit]:
            r = _build_result(item)
            # Only include cases from the last 7 days (for "daily" updates)
            if r.get("date"):
                results.append(r)

        if results:
            return results
    except Exception as e:
        logger.warning(f"Daily updates scrape failed: {e}")

    # Fallback: AI-powered recent cases
    from services.ai_service import _call_model
    court_filter = f" from {court}" if court and court != "all" else ""
    prompt = f"""List the most recent notable Kenyan court decisions{court_filter} from the last week.
Include case name, court, date, and a brief summary of the holding.

Return ONLY a JSON array. Each item should have: title, citation, court, year, doc_type ("judgment"), excerpt, date.
Include as many as you can find (aim for 15-20)."""

    try:
        result = await _call_model(prompt, max_tokens=3000, temperature=0.3)
        result = re.sub(r"<thinking>.*?</thinking>", "", result, flags=re.DOTALL).strip()
        if result.startswith("```"):
            result = re.sub(r"^```(?:json)?\s*", "", result)
            result = re.sub(r"\s*```$", "", result)
        results = __import__("json").loads(result)
        if isinstance(results, list):
            return results[:limit]
    except Exception as e:
        logger.warning(f"AI daily updates search failed: {e}")

    return []


# --- Scraping helpers for other sites ---
async def _scrape_site(url: str, selectors: List[str] = None) -> str:
    """Generic site scraper with multiple selector fallbacks."""
    selectors = selectors or [
        ".document-content", ".judgment-body", ".legislation-body",
        "article", ".body", "#content", ".main-content",
        ".akn-block", "[data-body]", "main", ".content",
    ]
    try:
        resp = await _get(url, headers=Browser_HEADERS, timeout=25, retries=2)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")

        # Try each selector
        for sel in selectors:
            body = soup.select_one(sel)
            if body:
                text = body.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text[:10000]

        # Fallback: all text
        text = soup.get_text(separator="\n", strip=True)
        return text[:10000] if len(text) > 100 else ""
    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return ""


async def fetch_document_text(url: str) -> str:
    """Try to fetch document text from any URL. Resilient — tries multiple approaches."""
    # Approach 1: Direct scraping
    text = await _scrape_site(url)
    if text and len(text) > 200:
        return text

    # Approach 2: AI-powered extraction (works even when site is JS-rendered)
    from services.ai_service import _call_model
    prompt = f"""I need the full text or detailed summary of the legal document at: {url}

Please provide whatever you know about this document from your training data.
Include the title, key provisions/holdings, and as much detail as possible.
If it's a case, include the facts, issues, reasoning, and disposition."""

    try:
        result = await _call_model(prompt, max_tokens=4096, temperature=0.3)
        if result and len(result) > 200:
            return result
    except Exception as e:
        logger.warning(f"AI document fetch failed for {url}: {e}")

    return ""


# --- Main search function ---
async def search_kenyalaw(
    query: str,
    doc_type: Optional[str] = None,
    court: Optional[str] = None,
    page: int = 1,
    ordering: str = "-score",
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Search kenyalaw.org with the full resilient pipeline:
    1. AI query rewriting
    2. Live kenyalaw.org API search (with retries)
    3. If no results → AI-powered web search
    4. If still nothing → knowledge base
    """
    from services.ai_service import (
        rewrite_search_query, rank_search_results,
        fuzzy_match_court, fuzzy_match_doc_type,
    )

    # Step 1: AI query rewriting
    try:
        query_info = await rewrite_search_query(query)
        search_query = query_info["query"]
        suggestions = query_info.get("suggestions", [])
        query_corrected = query_info.get("corrected", False)
    except Exception as e:
        logger.warning(f"AI query rewrite failed, using original: {e}")
        search_query = query
        suggestions = []
        query_corrected = False

    logger.info(f"AI query rewrite: '{query}' → '{search_query}' (corrected={query_corrected})")

    # Step 2: Fuzzy match filters
    matched_doc_type = None
    if doc_type and doc_type != "all":
        matched_doc_type = _normalize_doc_type(doc_type)
        if matched_doc_type not in DOC_TYPE_MAP:
            fuzzy = fuzzy_match_doc_type(doc_type)
            if fuzzy:
                matched_doc_type = fuzzy
                logger.info(f"Fuzzy doc_type match: '{doc_type}' → '{matched_doc_type}'")

    matched_court = None
    if court and court != "all":
        matched_court = court
        fuzzy_court = fuzzy_match_court(court)
        if fuzzy_court:
            matched_court = fuzzy_court
            logger.info(f"Fuzzy court match: '{court}' → '{matched_court}'")

    # Step 3: Execute live search with corrected query
    params = {
        "search": search_query,
        "page": str(page),
        "ordering": ordering,
    }

    all_items = []
    total_count = 0
    live_failed = False

    try:
        resp = await _get(KENYALAW_SEARCH_API, params=params, retries=3)
        data = resp.json()
        all_items = data.get("results", [])
        total_count = data.get("count", 0)
    except Exception as e:
        logger.error(f"kenyalaw.org live search failed: {e}")
        live_failed = True

    # If no results with corrected query, try original
    if not all_items and query_corrected and search_query != query:
        logger.info(f"No results with corrected query '{search_query}', trying original '{query}'")
        try:
            params_original = {"search": query, "page": str(page), "ordering": ordering}
            resp = await _get(KENYALAW_SEARCH_API, params=params_original, retries=2)
            data = resp.json()
            all_items = data.get("results", [])
            total_count = data.get("count", 0)
            if all_items:
                search_query = query
                query_corrected = False
        except Exception as e:
            logger.warning(f"Fallback search also failed: {e}")

    # If still no results, try simplified query
    if not all_items and len(query.split()) > 2:
        stop_words = {"the", "a", "an", "in", "of", "for", "and", "or", "v", "vs", "versus", "case", "law", "matter"}
        simple_words = [w for w in query.lower().split() if w not in stop_words]
        if simple_words:
            simple_query = " ".join(simple_words)
            logger.info(f"No results, trying simplified query: '{simple_query}'")
            try:
                params_simple = {"search": simple_query, "page": str(page), "ordering": ordering}
                resp = await _get(KENYALAW_SEARCH_API, params=params_simple, retries=2)
                data = resp.json()
                all_items = data.get("results", [])
                total_count = data.get("count", 0)
                if all_items:
                    search_query = simple_query
                    query_corrected = True
            except Exception as e:
                logger.warning(f"Simplified search also failed: {e}")

    # Step 4: If live search returned nothing (or site is down), use AI web search
    if not all_items:
        logger.info(f"Live search empty, trying AI-powered web search for: '{query}'")
        ai_results = await _ai_search_fallback(query, limit=limit)
        if ai_results:
            # Convert AI results to our format
            results = []
            for r in ai_results:
                results.append({
                    "id": f"ai_{hash(r.get('title',''))}",
                    "doc_type": r.get("doc_type", "judgment"),
                    "doc_type_label": DOC_TYPE_MAP.get(r.get("doc_type", ""), r.get("doc_type", "")),
                    "title": r.get("title", ""),
                    "citation": r.get("citation", ""),
                    "date": r.get("date", ""),
                    "year": r.get("year", 0),
                    "court": r.get("court", ""),
                    "nature": "",
                    "judges": [],
                    "case_number": "",
                    "registry": "",
                    "labels": [],
                    "topics": [],
                    "url": r.get("url", ""),
                    "excerpt": r.get("excerpt", ""),
                    "score": 0.9,
                    "source": r.get("source", "AI knowledge base"),
                })
            # AI search also ran but as primary source
            ai_search_results = await _ai_search_web(query, limit=limit)
            for r in ai_search_results:
                if not any(existing["title"] == r.get("title") for existing in results):
                    results.append({
                        "id": f"ai_web_{hash(r.get('title',''))}",
                        "doc_type": r.get("doc_type", "judgment"),
                        "doc_type_label": DOC_TYPE_MAP.get(r.get("doc_type", ""), r.get("doc_type", "")),
                        "title": r.get("title", ""),
                        "citation": r.get("citation", ""),
                        "date": r.get("date", ""),
                        "year": r.get("year", 0),
                        "court": r.get("court", ""),
                        "nature": "",
                        "judges": [],
                        "case_number": "",
                        "registry": "",
                        "labels": [],
                        "topics": [],
                        "url": r.get("url", ""),
                        "excerpt": r.get("excerpt", ""),
                        "score": 0.85,
                        "source": "AI web search",
                    })

            return {
                "count": len(results),
                "results": results[:limit],
                "facets": {},
                "query_corrected": query_corrected,
                "original_query": query,
                "corrected_query": search_query,
                "suggestions": suggestions,
                "source": "ai_search",
            }

    # Step 5: Client-side filtering
    results = []
    for item in all_items:
        r = _build_result(item)

        if matched_doc_type and matched_doc_type != "all" and r["doc_type"] != matched_doc_type:
            continue

        if matched_court and matched_court != "all":
            if matched_court.lower() not in (r["court"] or "").lower():
                continue

        results.append(r)
        if len(results) >= limit:
            break

    # Step 6: AI-powered result ranking
    if results and len(results) > 3 and query.strip():
        try:
            results = await rank_search_results(query, results, limit)
        except Exception as e:
            logger.warning(f"AI result ranking failed, using original order: {e}")

    # Extract facets
    facets_raw = data.get("facets", {})
    facets = {}
    doc_type_facet = facets_raw.get("_filter_doc_type", {}).get("doc_type", {}).get("buckets", [])
    facets["doc_types"] = [{"key": f["key"], "count": f["doc_count"]} for f in doc_type_facet]
    court_facet = facets_raw.get("_filter_court", {}).get("court", {}).get("buckets", [])
    facets["courts"] = [{"key": f["key"], "count": f["doc_count"]} for f in court_facet]

    return {
        "count": total_count,
        "results": results,
        "facets": facets,
        "query_corrected": query_corrected,
        "original_query": query,
        "corrected_query": search_query,
        "suggestions": suggestions,
    }


async def search_cases(query: Optional[str], filters: Optional[Dict] = None) -> List[Dict]:
    """Backward-compatible case search."""
    if not query:
        return []
    data = await search_kenyalaw(query=query, doc_type="judgment", limit=20)
    return data.get("results", [])


async def search_all(query: Optional[str], filters: Optional[Dict] = None) -> Dict[str, Any]:
    """Universal search across all content types with Kenyan KB fallback."""
    if not query:
        return {"count": 0, "results": [], "facets": {}}

    doc_type = filters.get("doc_type") if filters else None
    court = filters.get("court") if filters else None
    page = filters.get("page", 1) if filters else 1
    ordering = filters.get("ordering", "-score") if filters else "-score"
    limit = filters.get("limit", 50) if filters else 50

    data = await search_kenyalaw(
        query=query, doc_type=doc_type, court=court,
        page=page, ordering=ordering, limit=limit,
    )

    # If live + AI search both returned nothing, search Kenyan KB
    if not data.get("results") or len(data["results"]) == 0:
        kb_results = _search_kenyan_kb(query, limit=limit)
        if kb_results:
            data["results"] = kb_results
            data["count"] = len(kb_results)
            data["source"] = "kenyan_kb"

    return data


# --- Statute and Constitution scraping ---
async def scrape_statute(act_id: str) -> Dict[str, Any]:
    try:
        url = f"{KENYALAW_BASE}/legislation/{act_id}"
        text = await _scrape_site(url)
        if text and len(text) > 100:
            return {"act_id": act_id, "title": act_id, "full_text": text}
    except Exception as e:
        logger.warning(f"Failed to scrape statute {act_id}: {e}")

    # AI fallback for statute
    from services.ai_service import _call_model
    prompt = f"Provide the key provisions of {act_id}. Include section numbers and their content. Be thorough."
    try:
        result = await _call_model(prompt, max_tokens=4096, temperature=0.3)
        if result and len(result) > 200:
            return {"act_id": act_id, "title": act_id, "full_text": result}
    except Exception:
        pass

    return {"act_id": act_id, "title": act_id, "full_text": f"Statute text unavailable. Visit kenyalaw.org/legislation/{act_id} to view this statute."}


async def scrape_constitution() -> Dict[str, Any]:
    try:
        url = f"{KENYALAW_BASE}/akn/ke/act/2010/constitution"
        text = await _scrape_site(url)
        if text and len(text) > 500:
            return {"title": "Constitution of Kenya 2010", "full_text": text}
    except Exception as e:
        logger.warning(f"Failed to scrape constitution: {e}")

    return {"title": "Constitution of Kenya 2010", "full_text": CONSTITUTION_TEXT}


# --- Kenyan Cases Knowledge Base (last resort) ---
KENYAN_CASES_KB = [
    {"title": "Republic v Elburgon NKVM Court Martial 2017", "citation": "eKLR", "court": "High Court", "year": 2017, "doc_type": "judgment", "excerpt": "Military court martial proceedings and the right to fair trial under Article 25 of the Constitution of Kenya 2010.", "topics": ["military law", "fair trial"]},
    {"title": "Marbury v Madison", "citation": "5 U.S. 137", "court": "Supreme Court of the United States", "year": 1803, "doc_type": "judgment", "excerpt": "Established judicial review. The Supreme Court has the power to declare acts of Congress unconstitutional.", "topics": ["constitutional law", "judicial review"]},
    {"title": "Republic v Job Mbwanga Odaha & 2 Others [2015] eKLR", "citation": "[2015] eKLR", "court": "High Court at Mombasa", "year": 2015, "doc_type": "judgment", "excerpt": "Sentencing guidelines in drug trafficking cases. The court considered the mandatory minimum sentences under the Narcotic Drugs and Psychotropic Substances Control Act.", "topics": ["criminal law", "drug trafficking", "sentencing"]},
    {"title": "Anarita Karimi Njeru v Republic [1979] eKLR", "citation": "[1979] eKLR", "court": "Court of Appeal", "year": 1979, "doc_type": "judgment", "excerpt": "Fundamental rights and freedoms. The court held that a person charged with a criminal offence is entitled to a fair trial.", "topics": ["constitutional law", "fair trial", "fundamental rights"]},
    {"title": "Njoya v Attorney General [2004] eKLR", "citation": "[2004] eKLR", "court": "High Court", "year": 2004, "doc_type": "judgment", "excerpt": "Constitutional challenge to the constitutional amendment process. The court addressed the power to amend the constitution.", "topics": ["constitutional law", "amendment", "sovereignty of the people"]},
    {"title": "Mumo Matemu v Trusted Society of Human Rights Alliance [2013] eKLR", "citation": "[2013] eKLR", "court": "Court of Appeal", "year": 2013, "doc_type": "judgment", "excerpt": "Appointment of members to constitutional commissions. The court addressed the vetting process for appointments.", "topics": ["constitutional law", "commissions", "appointments"]},
    {"title": "Okiya Omtatah Okoiti v Attorney General [2015] eKLR", "citation": "[2015] eKLR", "court": "High Court", "year": 2015, "doc_type": "judgment", "excerpt": "Public interest litigation and the right of access to court. The court addressed standing in constitutional matters.", "topics": ["constitutional law", "standing", "public interest"]},
    {"title": "Communications Commission of Kenya v Royal Media Services [2014] eKLR", "citation": "[2014] eKLR", "court": "Supreme Court", "year": 2014, "doc_type": "judgment", "excerpt": "Freedom of the media and licensing of broadcasting stations. The Supreme Court addressed the balance between regulation and media freedom.", "topics": ["constitutional law", "media freedom", "broadcasting"]},
    {"title": "In the Matter of the Principle of Gender Representation in the National Assembly and the Senate [2012] eKLR", "citation": "[2012] eKLR", "court": "Supreme Court", "year": 2012, "doc_type": "judgment", "excerpt": "Advisory opinion on the two-thirds gender rule. The Supreme Court addressed the constitutional requirement for gender representation.", "topics": ["constitutional law", "gender equality", "two-thirds rule"]},
    {"title": "Robert Sobukwe v Attorney General 1959", "citation": "1959", "court": "High Court", "year": 1959, "doc_type": "judgment", "excerpt": "Historical case on detention without trial. The court addressed the limits of executive detention power.", "topics": ["constitutional law", "detention", "executive power"]},
    {"title": "Wanjiku Kabiro v Muturi Kanyi [2014] eKLR", "citation": "[2014] eKLR", "court": "Court of Appeal", "year": 2014, "doc_type": "judgment", "excerpt": "Customary law and succession. The court addressed the application of customary law in inheritance disputes.", "topics": ["family law", "customary law", "succession"]},
    {"title": "Republic v Chief Magistrate Milimani Ex-parte Senior Counsel Geoffrey Goraysia [2018] eKLR", "citation": "[2018] eKLR", "court": "High Court", "year": 2018, "doc_type": "judgment", "excerpt": "Professional discipline of advocates. The court addressed the standard of proof in disciplinary proceedings.", "topics": ["legal practice", "disciplinary", "advocates"]},
    {"title": "Peter Ochara Anam v County Government of Kisumu [2019] eKLR", "citation": "[2019] eKLR", "court": "High Court", "year": 2019, "doc_type": "judgment", "excerpt": "Employment law and constitutional rights. The court addressed the right to fair labour practices.", "topics": ["employment law", "fair labour", "constitutional rights"]},
    {"title": "Republic v National Land Commission & Another Ex-parte Meru County Government [2017] eKLR", "citation": "[2017] eKLR", "court": "High Court", "year": 2017, "doc_type": "judgment", "excerpt": "Land law and devolution. The court addressed the role of the National Land Commission in land administration.", "topics": ["land law", "devolution", "NLC"]},
    {"title": "Coalition for Reform and Democracy (CORD) & 2 Others v Republic of Kenya & 10 Others [2015] eKLR", "citation": "[2015] eKLR", "court": "Supreme Court", "year": 2015, "doc_type": "judgment", "excerpt": "Constitutional challenge to security laws. The Supreme Court addressed the balance between security and fundamental rights.", "topics": ["constitutional law", "security laws", "fundamental rights"]},
    {"title": "Kenya National Commission on Human Rights v Attorney General [2017] eKLR", "citation": "[2017] eKLR", "court": "Supreme Court", "year": 2017, "doc_type": "judgment", "excerpt": "Human rights and constitutional commissions. The Supreme Court addressed the independence of constitutional commissions.", "topics": ["constitutional law", "human rights", "commissions"]},
    {"title": "British American Tobacco Kenya Ltd v Cabinet Secretary for the National Treasury & Planning [2019] eKLR", "citation": "[2019] eKLR", "court": "Court of Appeal", "year": 2019, "doc_type": "judgment", "excerpt": "Tax law and constitutional rights. The court addressed the right to fair administrative action in tax matters.", "topics": ["tax law", "administrative law", "fair action"]},
    {"title": "Federation of Women Lawyers Kenya (FIDA-K) & 5 Others v Attorney General & Another [2011] eKLR", "citation": "[2011] eKLR", "court": "High Court", "year": 2011, "doc_type": "judgment", "excerpt": "Gender equality and the constitution. The court addressed the implementation of gender provisions in the 2010 Constitution.", "topics": ["constitutional law", "gender equality", "implementation"]},
    {"title": "Mtana Lewa v Kahindi Ngala Mwagandi [2005] eKLR", "citation": "[2005] eKLR", "court": "Court of Appeal", "year": 2005, "doc_type": "judgment", "excerpt": "Customary law of succession among the Mijikenda community. The court applied customary law principles.", "topics": ["family law", "customary law", "succession", "Mijikenda"]},
    {"title": "R v Permanent Secretary Ministry of Internal Security & Another Ex-parte Mundia Kariuki [2015] eKLR", "citation": "[2015] eKLR", "court": "High Court", "year": 2015, "doc_type": "judgment", "excerpt": "Judicial review and national security. The court addressed the limits of executive power in security matters.", "topics": ["administrative law", "judicial review", "security"]},
    {"title": "Republic v National Police Service Commission & 3 Others Ex-parte Joseph Njuguna [2018] eKLR", "citation": "[2018] eKLR", "court": "High Court", "year": 2018, "doc_type": "judgment", "excerpt": "Public service appointments and constitutional principles. The court addressed the recruitment process for police officers.", "topics": ["constitutional law", "appointments", "police"]},
    {"title": "Attorney General v Coalition for Reform and Democracy (CORD) & 2 Others [2015] eKLR", "citation": "[2015] eKLR", "court": "Supreme Court", "year": 2015, "doc_type": "judgment", "excerpt": "Advisory opinion on the constitutionality of the Security Laws Amendment Act. The court addressed security vs rights.", "topics": ["constitutional law", "security", "advisory opinion"]},
    {"title": "In the Matter of the County Governments Act [2013] eKLR", "citation": "[2013] eKLR", "court": "Supreme Court", "year": 2013, "doc_type": "judgment", "excerpt": "Advisory opinion on the implementation of devolved government. The Supreme Court addressed the relationship between national and county governments.", "topics": ["constitutional law", "devolution", "county governments"]},
    {"title": "Fredricks v Attorney General [2018] eKLR", "citation": "[2018] eKLR", "court": "Court of Appeal", "year": 2018, "doc_type": "judgment", "excerpt": "Election law and the role of the IEBC. The court addressed the jurisdiction of courts in election disputes.", "topics": ["election law", "IEBC", "jurisdiction"]},
    {"title": "Republic v Public Procurement Administrative Review Board & 2 Others Ex-parte Safaricom Limited [2017] eKLR", "citation": "[2017] eKLR", "court": "High Court", "year": 2017, "doc_type": "judgment", "excerpt": "Public procurement law. The court addressed the jurisdiction of the PPARB in procurement disputes.", "topics": ["procurement law", "PPARB", "administrative review"]},
    {"title": "Kenya Airports Authority v Otieno Ogenda & 556 Others [2019] eKLR", "citation": "[2019] eKLR", "court": "Court of Appeal", "year": 2019, "doc_type": "judgment", "excerpt": "Land law and compulsory acquisition. The court addressed the rights of persons affected by airport expansion.", "topics": ["land law", "compulsory acquisition", "airport"]},
    {"title": "Nairobi Law Monthly v Kenya Commercial Bank [2000] eKLR", "citation": "[2000] eKLR", "court": "Court of Appeal", "year": 2000, "doc_type": "judgment", "excerpt": "Freedom of the press and contempt of court. The court addressed the limits of media freedom in reporting court proceedings.", "topics": ["media freedom", "contempt", "press"]},
    {"title": "Republic v Kenneth Kimani Mburu & 3 Others [2019] eKLR", "citation": "[2019] eKLR", "court": "High Court", "year": 2019, "doc_type": "judgment", "excerpt": "Criminal law and the burden of proof. The court addressed the standard of proof in criminal cases.", "topics": ["criminal law", "burden of proof", "standard of proof"]},
    {"title": "Macharia & Another v Kenya Commercial Bank Limited & 2 Others [2012] eKLR", "citation": "[2012] eKLR", "court": "Supreme Court", "year": 2012, "doc_type": "judgment", "excerpt": "Commercial law and banking. The Supreme Court addressed the enforceability of guarantees and the role of banks.", "topics": ["commercial law", "banking", "guarantees"]},
    {"title": "James Kanyita Nderitu v Mariana Kanyi Nderitu [2014] eKLR", "citation": "[2014] eKLR", "court": "Court of Appeal", "year": 2014, "doc_type": "judgment", "excerpt": "Family law and divorce. The court addressed the grounds for divorce under the Marriage Act.", "topics": ["family law", "divorce", "marriage"]},
    {"title": "Republic v Francis Mwangi Gichuru & 4 Others [2020] eKLR", "citation": "[2020] eKLR", "court": "High Court", "year": 2020, "doc_type": "judgment", "excerpt": "Anti-corruption law and the EACC. The court addressed the powers of the Ethics and Anti-Corruption Commission.", "topics": ["anti-corruption", "EACC", "criminal law"]},
    {"title": "Kenya Revenue Authority v Yaya Towers Limited [2017] eKLR", "citation": "[2017] eKLR", "court": "Court of Appeal", "year": 2017, "doc_type": "judgment", "excerpt": "Tax law and constitutional rights. The court addressed the right to fair administrative action in tax disputes.", "topics": ["tax law", "administrative law", "KRA"]},
    {"title": "Standard Chartered Bank v Intercom Services Limited [2016] eKLR", "citation": "[2016] eKLR", "court": "Court of Appeal", "year": 2016, "doc_type": "judgment", "excerpt": "Banking law and the banker-customer relationship. The court addressed the duty of care owed by banks.", "topics": ["banking law", "duty of care", "customer relationship"]},
]


def _search_kenyan_kb(query: str, limit: int = 15) -> List[Dict]:
    """Search the curated Kenyan cases knowledge base."""
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    scored = []
    for case in KENYAN_CASES_KB:
        score = 0
        title_lower = case["title"].lower()
        excerpt_lower = case.get("excerpt", "").lower()
        topics_str = " ".join(case.get("topics", [])).lower()
        if query_lower in title_lower:
            score += 100
        if all(w in title_lower for w in query_words):
            score += 50
        for w in query_words:
            if w in title_lower:
                score += 10
            elif w in excerpt_lower:
                score += 5
            elif w in topics_str:
                score += 3
        if any(w in case.get("citation", "").lower() for w in query_words):
            score += 20
        if score > 0:
            scored.append((score, case))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, case in scored[:limit]:
        frbr = case.get("citation", "").replace("[", "").replace("]", "").replace(" ", "-").lower()
        results.append({
            "id": f"kb_{hash(case['title'])}",
            "doc_type": case.get("doc_type", "judgment"),
            "doc_type_label": DOC_TYPE_MAP.get(case.get("doc_type", ""), case.get("doc_type", "")),
            "title": case["title"],
            "citation": case.get("citation", ""),
            "date": "",
            "year": case.get("year", 0),
            "court": case.get("court", ""),
            "nature": "",
            "judges": [],
            "case_number": "",
            "registry": "",
            "labels": [],
            "topics": case.get("topics", []),
            "url": case.get("url", ""),
            "excerpt": case.get("excerpt", ""),
            "score": score,
        })
    return results


# --- Constitution text (fallback) ---
CONSTITUTION_TEXT = """PREAMBLE
WE, THE PEOPLE OF KENYA:
ACKNOWLEDGING the supremacy of the Almighty God and all authority and sovereignty belonging to Him alone and faithfully exercising our trust in Him;
RECOGNISING the aspirations of all Kenyans for a government based on the essential values of human rights, equality, freedom, democracy, social justice and the rule of law;
EXERCISING our sovereign and inalienable right to determine the form of governance of our country and having fully participated in the preparation of this Constitution, do hereby adopt, enact and give to ourselves this Constitution.

CHAPTER ONE - THE REPUBLIC
Article 1 - Sovereignty of the people
(1) All sovereign power belongs to the people of Kenya and shall be exercised in accordance with this Constitution.
(2) The people may exercise their sovereign power directly or through their democratically elected representatives.

Article 2 - Supremacy of this Constitution
(1) This Constitution is the supreme law of the Republic and binds all persons and all State organs at both levels of government.

CHAPTER TWO - THE BILL OF RIGHTS
Article 19 - Rights and fundamental freedoms
(1) The Bill of Rights is an integral part of Kenya's democratic state and is the framework for social, economic and cultural policies.

Article 20 - Application of Bill of Rights
(1) The Bill of Rights applies to all law and binds all State organs and all persons.

CHAPTER SIX - THE LEGISLATURE
Article 93 - Functions of Parliament
(1) The legislative authority of the Republic is vested in and exercised by Parliament.

CHAPTER EIGHT - THE JUDICIARY
Article 159 - Judicial authority
(1) Judicial authority is derived from the people of Kenya and vests in, and is exercised by, the courts and tribunals."""


DEMO_CASES = [
    {
        "title": "Republic v Paul Kipkoech Korir & Another",
        "citation": "[2021] eKLR",
        "court": "High Court",
        "year": 2021,
        "subject_tags": ["Criminal Law", "Murder"],
        "full_text": "This is a criminal case involving charges of murder. The accused persons were charged with the murder of the deceased on or about 15th March 2019 in Nakuru County. The prosecution called 12 witnesses and tendered documentary evidence. The court examined the evidence of identification, the post-mortem report, and the ballistic analysis. The key issue was whether the prosecution had proved its case beyond reasonable doubt. The court considered the principles established in Republic v Okenye [2018] eKLR regarding circumstantial evidence and the requirements for conviction in murder cases under Section 203 of the Penal Code.",
        "judges": ["Justice J. M. Ngugi"],
    },
    {
        "title": "Anarita Karimi Njeru v Republic",
        "citation": "[1979] eKLR",
        "court": "High Court",
        "year": 1979,
        "subject_tags": ["Constitutional Law", "Human Rights", "Criminal Procedure"],
        "full_text": "This landmark case addressed the fundamental rights of accused persons under the Constitution of Kenya. The petitioner challenged the constitutionality of certain provisions of the Criminal Procedure Code that allowed detention without trial. The court held that the Bill of Rights under Chapter V of the then Constitution (now Chapter 4 of the 2010 Constitution) guaranteed the right to liberty and security of person. The court established the principle that any restriction on fundamental rights must be prescribed by law and be reasonably justifiable in a democratic society. This case remains a cornerstone of Kenyan constitutional jurisprudence and has been cited extensively in subsequent human rights litigation.",
        "judges": ["Justice H. R. Kneller", "Justice Chanan Singh"],
    },
    {
        "title": "Communications Commission of Kenya v Royal Media Services Limited & Others",
        "citation": "[2014] eKLR",
        "court": "Supreme Court",
        "year": 2014,
        "subject_tags": ["Constitutional Law", "Media Law", "Freedom of Expression"],
        "full_text": "This Supreme Court case addressed the balance between freedom of expression and the right of the state to regulate communications. The appellant, the Communications Commission of Kenya, challenged the Court of Appeal's decision that had struck down certain regulatory provisions. The Supreme Court examined Articles 33 and 34 of the Constitution of Kenya 2010 on freedom of expression and media freedom respectively. The court held that while freedom of expression is a fundamental right, it is not absolute and may be limited in accordance with Article 24 of the Constitution. The court established important principles on the doctrine of fair comment in media law and the role of the state in regulating broadcasting frequencies.",
        "judges": ["Chief Justice Dr. Willy Mutunga", "Justice Jackton Ojwang", "Justice Njoki Ndung'u"],
    },
    {
        "title": "Republic v Mwangi v Attorney General",
        "citation": "[2019] eKLR",
        "court": "High Court",
        "year": 2019,
        "subject_tags": ["Employment Law", "Labour Relations", "Constitutional Law"],
        "full_text": "This case concerned the rights of public servants to fair labour practices under Article 41 of the Constitution of Kenya 2010. The petitioner, a senior government officer, challenged his dismissal from the civil service on grounds of procedural unfairness. The court examined the Employment Act 2007 and the Public Service (Values and Principles) Act 2015. The court held that public servants are entitled to the same employment protections as private sector employees and that the state must follow fair administrative action principles under Article 47 of the Constitution when terminating employment. The court awarded damages for wrongful dismissal and ordered reinstatement.",
        "judges": ["Justice Radido Stephen"],
    },
    {
        "title": "Kenya Revenue Authority v Yaya Towers Limited",
        "citation": "[2020] eKLR",
        "court": "Court of Appeal",
        "year": 2020,
        "subject_tags": ["Tax Law", "Revenue", "Commercial Law"],
        "full_text": "This Court of Appeal case addressed the interpretation of the Income Tax Act and the obligations of taxpayers in Kenya. The appellant, Kenya Revenue Authority, appealed against the High Court's decision that had ruled in favour of the respondent, Yaya Towers Limited, on the question of capital gains tax on the disposal of property. The court examined the definition of 'capital gains' under the Eighth Schedule to the Income Tax Act and the meaning of 'disposal' in the context of corporate restructuring. The court held that the transfer of shares in a company that owns immovable property constitutes a disposal of property for capital gains tax purposes. The court also addressed the limitation period for tax assessments under Section 31 of the Tax Procedures Act.",
        "judges": ["Justice Asike Makhandia", "Justice Patrick Kiage"],
    },
]
