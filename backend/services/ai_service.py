"""AI service — wraps NVIDIA / OpenAI-compatible chat completions with:
- shared httpx connection pool (lifetime = process)
- semi-persistent in-memory LRU response cache (configurable TTL)
- dual-model fallback with structured error handling
- all public helpers remain async-await for caller compatibility

Public contract (unchanged):
    init_ai(), init_backend()
    generate_case_summary(full_text)
    generate_study_notes(full_text)
    generate_citation(case_data)
    compare_cases(text_a, text_b)
    generate_flashcard(case_data)
    generate_summary_from_metadata(...)
    extract_key_quotes(text, max_quotes)
    rewrite_search_query(query)
    rank_search_results(query, results, top_n)
    fuzzy_match_term / fuzzy_match_court / fuzzy_match_doc_type / search_similar
    legal_research_assistant, format_citation, explain_legal_concept,
    compare_jurisdictions, generate_legal_memo, analyze_case_law,
    interpret_statute, generate_study_plan, translate_legal_term
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

from cache import ai_cache, _stable_key
from core import settings as _core_settings

logger = logging.getLogger("juriscore.ai")

# ─────────────────────────────────────────────────────────────────────────────
# Lazy singleton HTTP client (one per worker; reused across all AI calls)
# ─────────────────────────────────────────────────────────────────────────────
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=_core_settings.AI_TIMEOUT_SECONDS,
                write=30.0,
                pool=10.0,
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=5,
                keepalive_expiry=30.0,
            ),
            follow_redirects=True,
        )
    return _http_client


# ─────────────────────────────────────────────────────────────────────────────
# Configuration (all from core.settings; no free-floating os.getenv)
# ─────────────────────────────────────────────────────────────────────────────
_API_KEY: str = ""
_BASE_URL: str = _core_settings.AI_BASE_URL
_MODEL: str   = _core_settings.AI_MODEL
_FALLBACK: str = _core_settings.AI_FALLBACK_MODEL
_AI_CACHE_TTL: int = _core_settings.AI_CACHE_TTL_SECONDS


HUMANIZE_SYSTEM = """
You are a senior Kenyan legal scholar who writes with genuine authority.
CRITICAL WRITING RULES:
- VARY sentence length dramatically. Never let 4 consecutive sentences be similar length.
- NEVER use: delve, furthermore, moreover, utilize, leverage, robust, pivotal,
  paramount, comprehensive, seamless, holistic, tapestry, journey, game-changer,
  groundbreaking, nuanced, multifaceted.
- NEVER start paragraphs with: Furthermore, Moreover, In addition,
  It is important to note, Having said that.
- NEVER end with: In conclusion, As we have seen, To sum up.
- COMMIT to positions. Say "the court got this wrong" not "it may be questioned".
- Be SPECIFIC. Name cases, dates, numbers, judges. Not "recent developments"
  but "the March 2026 ruling in Republic v Odaha".
- USE contractions naturally: don't, can't, it's, they've.
- PUNCTUATION: Use em dashes (—), semicolons (;), parenthetical asides.
- Write with temperature: firm when arguing, puzzled when describing complexity.
- One deliberate imperfection per section: a fragment, starting with "But" or "So".
- For Kenyan law: cite as Case Name [Year] KEHC/KECA number (KLR).
  Reference the Constitution of Kenya 2010 by article number.""".strip()


QUERY_REWRITE_SYSTEM = """
You are a legal search assistant for KenyaLaw.org. Correct and expand a user's
search query. Fix typos, expand abbreviations (MR → Mining Regulations), and
add relevant legal context.
Return ONLY: {"query": str, "suggestions": [str, str, str], "reasoning": str}"""


RANK_SYSTEM = """
You are a legal research expert. Rank these search results by relevance to the
user query. Think step by step for each result. Return a JSON array of indices
(most relevant first)."""


LEGAL_RESEARCH_SYSTEM = """
You are a world-class legal research assistant with expertise across common law,
civil law, and African legal systems. Provide precise, well-cited analysis.
Always cite specific cases, statutes, or articles.""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Initialisation
# ─────────────────────────────────────────────────────────────────────────────

def init_ai() -> None:
    """Call once at application startup after core.settings is ready."""
    global _API_KEY
    _API_KEY = _core_settings.NVIDIA_API_KEY or _core_settings.OPENAI_API_KEY
    if _API_KEY:
        model_tag = _MODEL
        logger.info("AI service ready (model=%s)", model_tag)
    else:
        logger.warning("AI service disabled — no API key configured")


# Backwards-compat alias
init_backend = init_ai


# ─────────────────────────────────────────────────────────────────────────────
# Core model call (with retry, fallback, and caching)
# ─────────────────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=4096)
def _prompt_fingerprint(prompt: str, max_tokens: int, system: Optional[str], temperature: float) -> str:
    """Cache-key for prompt+settings combination (pure, no I/O)."""
    blob = json.dumps(
        {"p": prompt, "mt": max_tokens, "s": system, "t": temperature},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


async def _call_model(
    prompt: str,
    max_tokens: int = 1024,
    system: Optional[str] = None,
    temperature: float = 0.7,
    cache: bool = True,
) -> str:
    """Call the configured model (or fallback). Returns plain text content."""
    if not _API_KEY:
        logger.warning("_call_model invoked with no API key — returning empty string")
        return ""

    fp = _prompt_fingerprint(prompt, max_tokens, system, temperature)
    if cache:
        cached_text = ai_cache.get(fp)
        if cached_text is not None:
            logger.debug("AI cache hit (fp=%s)", fp[:12])
            return cached_text

    client = _get_client()

    for model in (_MODEL, _FALLBACK):
        try:
            messages = [
                {"role": "system", "content": system or HUMANIZE_SYSTEM},
                {"role": "user",   "content": prompt},
            ]
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.9,
            }
            headers = {
                "Authorization": f"Bearer {_API_KEY}",
                "Content-Type": "application/json",
            }
            resp = await client.post(
                f"{_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            content: str = data["choices"][0]["message"]["content"].strip()
            content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL).strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            if content and len(content) > 5:
                if cache:
                    ai_cache.set(fp, content, ttl_seconds=_AI_CACHE_TTL)
                logger.debug("AI call OK via %s (fp=%s)", model, fp[:12])
                return content
            logger.warning("Model %s returned empty response, trying next", model)
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Model %s HTTP %s: %.200s", model, exc.response.status_code, exc.response.text
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Model %s failed: %s: %s", model, type(exc).__name__, exc)

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# JSON parsing helper
# ─────────────────────────────────────────────────────────────────────────────

def _json(text: str, fallback: Any = None) -> Any:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return fallback


# ─────────────────────────────────────────────────────────────────────────────
# Case summary / study notes
# ─────────────────────────────────────────────────────────────────────────────

async def generate_case_summary(full_text: str) -> Dict[str, Any]:  # noqa: C901
    prompt = f"""Analyse this Kenyan legal case using IRAC.
Return ONLY valid JSON with:
  facts, issues, rule, application, conclusion, ratio, obiter,
  cases_cited (list), significance (string).

Case text: {full_text[:6000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k, default in [
            ("facts", ""), ("issues", []), ("rule", ""),
            ("application", ""), ("conclusion", ""), ("ratio", ""),
            ("obiter", ""), ("cases_cited", []), ("significance", ""),
        ]:
            parsed.setdefault(k, default)
        return parsed
    return {"facts": "Summary generation is temporarily unavailable.", "issues": [],
            "rule": "", "application": "", "conclusion": "", "ratio": "",
            "obiter": "", "cases_cited": [], "significance": ""}


async def generate_study_notes(full_text: str) -> Dict[str, Any]:
    prompt = f"""Create exam-ready study notes for this case.
Return ONLY valid JSON with:
  facts (string), issues (list), rule,
  application, conclusion, ratio, key_quotes (list, max 40 words each),
  significance (string).

Case text: {full_text[:6000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k, default in [
            ("facts", ""), ("issues", []), ("rule", ""),
            ("application", ""), ("conclusion", ""), ("ratio", ""),
            ("key_quotes", []), ("significance", ""),
        ]:
            parsed.setdefault(k, default)
        return parsed
    return {"facts": "", "issues": [], "rule": "", "application": "",
            "conclusion": "", "ratio": "", "key_quotes": [], "significance": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Citation
# ─────────────────────────────────────────────────────────────────────────────

async def generate_citation(case_data: Dict) -> Dict[str, str]:
    prompt = (
        "Format this case data into a proper Kenyan eKLR citation. "
        f"Case data: {json.dumps(case_data)[:2000]}\nReturn ONLY valid JSON with "
        "keys: parties, year, court, neutral_citation, formatted."
    )
    raw = await _call_model(prompt, temperature=0.3)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k in ("parties", "year", "court", "neutral_citation", "formatted"):
            parsed.setdefault(k, "")
        return parsed
    return {"parties": "", "year": "", "court": "", "neutral_citation": "", "formatted": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Case comparison
# ─────────────────────────────────────────────────────────────────────────────

async def compare_cases(case_a_text: str, case_b_text: str) -> Dict[str, Any]:
    prompt = (
        "Compare these two Kenyan cases. Analyse whether they are consistent, "
        "distinguishable, or in tension. "
        f"Case A: {case_a_text[:4000]}\n\nCase B: {case_b_text[:4000]}\n\n"
        "Return ONLY valid JSON with: similarities, differences, "
        "legal_proposition_a, legal_proposition_b, recommendation."
    )
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k in ("similarities", "differences", "legal_proposition_a",
                  "legal_proposition_b", "recommendation"):
            parsed.setdefault(k, [] if k in ("similarities", "differences") else "")
        return parsed
    return {"similarities": [], "differences": [],
            "legal_proposition_a": "", "legal_proposition_b": "", "recommendation": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Flashcard
# ─────────────────────────────────────────────────────────────────────────────

async def generate_flashcard(case_data: Dict) -> Dict[str, str]:
    prompt = (
        "From this case create ONE flashcard for exam revision. "
        f"Case: {json.dumps(case_data)[:2000]}\n"
        'Return ONLY valid JSON with keys: "front" (max 20 words) and "back" (max 60 words).'
    )
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        parsed.setdefault("front", "What is the holding?")
        parsed.setdefault("back", "TBD")
        return parsed
    return {"front": "What is the holding?", "back": "TBD"}


# ─────────────────────────────────────────────────────────────────────────────
# Metadata summary
# ─────────────────────────────────────────────────────────────────────────────

async def generate_summary_from_metadata(
    title: str,
    citation: str,
    court: str,
    date: str,
    doc_type: str,
    excerpt: str = "",
) -> str:
    prompt = f"""Analyse this Kenyan legal document using IRAC.
Write plain text only. No markdown. No **bold*. 3-4 paragraphs.

- Title: {title}
- Citation: {citation}
- Court: {court}
- Date: {date}
- Type: {doc_type}
- Excerpt: {excerpt}"""
    result = await _call_model(prompt, max_tokens=800, temperature=0.6, cache=True)
    return result if result else f"Summary unavailable for: {title}"


# ─────────────────────────────────────────────────────────────────────────────
# Key quotes
# ─────────────────────────────────────────────────────────────────────────────

async def extract_key_quotes(text: str, max_quotes: int = 5) -> List[str]:
    prompt = (
        f"Extract up to {max_quotes} key legal quotes (max 40 words each). "
        f"Return ONLY a JSON array of strings.\n{text[:6000]}\nJSON:"
    )
    raw = await _call_model(prompt, max_tokens=512, temperature=0.4)
    parsed = _json(raw, [])
    return parsed[:max_quotes] if isinstance(parsed, list) else []


# ─────────────────────────────────────────────────────────────────────────────
# AI search
# ─────────────────────────────────────────────────────────────────────────────

async def rewrite_search_query(query: str) -> Dict[str, Any]:
    if not _API_KEY or len(query.strip()) < 2:
        return {"query": query, "suggestions": [], "corrected": False}
    prompt = (
        f'Correct and improve this legal search query for KenyaLaw.org: "{query}"\n'
        "Return JSON: {\"query\": str, \"suggestions\": [..3], \"reasoning\": str}"
    )
    raw = await _call_model(
        prompt, max_tokens=300, system=QUERY_REWRITE_SYSTEM, temperature=0.3
    )
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        q = parsed.get("query", query).strip()
        return {
            "query": q,
            "suggestions": parsed.get("suggestions", [])[:3],
            "corrected": q.lower().replace(" ", "") != query.lower().replace(" ", ""),
        }
    return {"query": query, "suggestions": [], "corrected": False}


async def rank_search_results(
    query: str, results: List[Dict], top_n: int = 30
) -> List[Dict]:
    if not _API_KEY or not results:
        return results
    if len(results) > top_n:
        results = results[:top_n]

    listing = "\n".join(
        f"[{i}] {r.get('title','Untitled')} | {r.get('court','?')} | "
        f"{r.get('doc_type','?')} | {r.get('date','?')} | {r.get('excerpt','')[:100]}"
        for i, r in enumerate(results)
    )
    prompt = (
        f"Rank by relevance to: \"{query}\"\n{listing}\n"
        f"Return ONLY a JSON array of indices (most relevant first, max {top_n})."
    )
    raw = await _call_model(
        prompt, max_tokens=500, system=RANK_SYSTEM, temperature=0.3
    )
    parsed = _json(raw, [])
    if isinstance(parsed, list):
        ranked: List[Dict] = []
        seen: set = set()
        for idx in parsed:
            if isinstance(idx, int) and 0 <= idx < len(results) and idx not in seen:
                ranked.append(results[idx])
                seen.add(idx)
        for i, r in enumerate(results):
            if i not in seen:
                ranked.append(r)
        return ranked[:top_n]
    return results[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy matching
# ─────────────────────────────────────────────────────────────────────────────

from difflib import SequenceMatcher


def fuzzy_match_term(
    term: str, candidates: List[str], threshold: float = 0.5
) -> Optional[str]:
    term_lower = term.lower().strip()
    best_match = None
    best_score = 0.0
    term_words = set(term_lower.split())

    for candidate in candidates:
        cl = candidate.lower().strip()
        if term_lower == cl:
            return candidate
        if term_lower in cl or cl in term_lower:
            score = 0.9
        else:
            score = SequenceMatcher(None, term_lower, cl).ratio()
        if term_words & set(cl.split()):
            score = max(score, 0.75)
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score >= threshold else None


KNOWN_COURTS = [
    "Supreme Court", "Court of Appeal", "High Court",
    "Environment and Land Court", "Employment and Labour Relations Court",
    "Magistrate Court", "Kadhi Court", "Military Court", "Tribunal",
    "Industrial Court", "Commercial Court", "Constitutional Court",
    "Family Court", "Criminal Division", "Civil Division",
    "Judicial Review Division", "Anti-Corruption Court", "Drug Traffic Court",
    "Tax Tribunal", "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret",
    "Nyeri", "Machakos", "Meru",
]

KNOWN_DOC_TYPES = [
    "judgment", "legislation", "gazette", "bill",
    "generic_document", "journal", "causelist", "case law",
    "act", "regulation", "statute",
]

DOC_TYPE_ALIASES = {
    "case": "judgment", "cases": "judgment", "judgement": "judgment",
    "judge": "judgment", "court": "judgment", "ruling": "judgment",
    "statute": "legislation", "act": "legislation", "acts": "legislation",
    "law": "legislation", "statutes": "legislation",
    "regulation": "regulation", "regulations": "regulation",
    "subsidiary": "regulation",
    "treaty": "treaty", "treaties": "treaty",
    "convention": "treaty",
    "decision": "decision", "decisions": "decision",
    "article": "article", "articles": "article",
    "cause list": "causelist", "causelists": "causelist",
    "publication": "generic_document", "publications": "generic_document",
}


def fuzzy_match_court(court_input: str) -> Optional[str]:
    return fuzzy_match_term(court_input, KNOWN_COURTS, threshold=0.45)


def fuzzy_match_doc_type(type_input: str) -> Optional[str]:
    lower = type_input.lower().strip()
    if lower in DOC_TYPE_ALIASES:
        return DOC_TYPE_ALIASES[lower]
    return fuzzy_match_term(lower, KNOWN_DOC_TYPES, threshold=0.45)


def search_similar(query: str, cases: List[Dict]) -> List[str]:
    q_terms = set(re.findall(r"\w+", query.lower()))
    scored = []
    for c in cases:
        text = " ".join([c.get("title", ""), c.get("full_text", "")]).lower()
        c_terms = set(re.findall(r"\w+", text))
        scored.append((len(q_terms & c_terms), c.get("id", "")))
    scored.sort(reverse=True)
    return [cid for _, cid in scored]


# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive AI tools
# ─────────────────────────────────────────────────────────────────────────────

async def legal_research_assistant(query: str, jurisdiction: str = "kenya") -> Dict[str, Any]:
    prompt = f"""Provide legal research on: "{query}" for {jurisdiction}.
Format as JSON: {{
  "legal_framework": str,
  "key_cases": [{{"name": str, "citation": str, "principle": str}}],
  "legal_principles": [str],
  "practical_implications": str,
  "related_topics": [str]
}}"""
    raw = await _call_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k, default in [
            ("legal_framework", "Research temporarily unavailable"),
            ("key_cases", []),
            ("legal_principles", []),
            ("practical_implications", ""),
            ("related_topics", []),
        ]:
            parsed.setdefault(k, default)
        return parsed
    return {"legal_framework": "Research temporarily unavailable", "key_cases": [],
            "legal_principles": [], "practical_implications": "", "related_topics": []}


async def format_citation(case_data: Dict, jurisdiction: str = "kenya") -> str:
    rules = {
        "kenya": "Case Name [Year] eKLR",
        "nigeria": "Case Name [Year] LPELR-XXXX",
        "south_africa": "Case Name [Year] ZACC/ZZA/ZZG",
        "uk": "Case Name [Year] UKSC/UKHL/EWCA",
        "us": "Case Name Volume Reporter Page (Court Year)",
        "india": "Case Name (Year) SCC",
        "international": "Case Name [Year] ICJ/ECtHR/AfCHPR",
    }
    fmt = rules.get(jurisdiction, rules["kenya"])
    prompt = f"""Format citation for {jurisdiction} (rule: {fmt}).
Case: {json.dumps(case_data)}
Return ONLY the formatted citation string."""
    result = await _call_model(prompt, max_tokens=200, temperature=0.2)
    return result or f"{case_data.get('title','Unknown')} [{case_data.get('year','Year')}] {jurisdiction.title()} Reports"


async def explain_legal_concept(concept: str, jurisdiction: str = "kenya") -> str:
    prompt = f"""Explain "{concept}" for {jurisdiction} law students.
1. Definition in plain language.
2. How it applies in {jurisdiction}.
3. Key cases.
4. Common exam questions.
5. Practical examples.
Be direct and specific."""
    result = await _call_model(
        prompt, max_tokens=800, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5
    )
    return result if result else f"Explanation unavailable for: {concept}"


async def compare_jurisdictions(
    legal_issue: str, jurisdictions: Optional[List[str]] = None
) -> Dict[str, Any]:
    jurisdictions = jurisdictions or ["kenya", "nigeria", "south_africa", "uk", "us"]
    prompt = (
        f"Compare how {', '.join(jurisdictions)} handle: \"{legal_issue}\"\n"
        "Format as JSON: {"
        '"issue": str, "comparisons": {jurisdiction: {"law": str, "interpretation": str,'
        ' "key_cases": [str], "unique_aspect": str}},'
        ' "key_differences": [str], "trend": str}'
    )
    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        parsed.setdefault("issue", legal_issue)
        parsed.setdefault("comparisons", {})
        parsed.setdefault("key_differences", [])
        parsed.setdefault("trend", "")
        return parsed
    return {"issue": legal_issue, "comparisons": {}, "key_differences": [], "trend": ""}


async def generate_legal_memo(issue: str, facts: str = "", jurisdiction: str = "kenya") -> str:
    prompt = f"""Write a legal memorandum for {jurisdiction}.
Issue: {issue}
{"Facts: " + facts if facts else ""}
Structure: 1. ISSUE(S) PRESENTED  2. BRIEF ANSWER  3. FACTS (if any)
4. DISCUSSION — applicable law, case law, application to facts
5. CONCLUSION. Be direct, cite specific cases."""
    result = await _call_model(
        prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5
    )
    return result or f"Legal memo generation unavailable for: {issue}"


async def analyze_case_law(case_text: str, jurisdiction: str = "kenya") -> Dict[str, Any]:
    prompt = f"""Deep analysis of this {jurisdiction} case:
{case_text[:5000]}
Return ONLY valid JSON:
{{"facts": str, "issues": [str], "holdings": [str], "ratio": str,
 "obiter": str, "significance": str, "critique": str,
 "application": str, "related_cases": [str], "exam_relevance": [str]}}"""
    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k in ("facts", "issues", "holdings", "ratio", "obiter", "significance",
                  "critique", "application", "related_cases", "exam_relevance"):
            parsed.setdefault(k, [] if k in ("issues", "holdings", "related_cases", "exam_relevance") else "")
        return parsed
    return {"facts": "", "issues": [], "holdings": [], "ratio": "", "obiter": "",
            "significance": "", "critique": "", "application": "",
            "related_cases": [], "exam_relevance": []}


async def interpret_statute(
    statute_text: str, section: str = "", jurisdiction: str = "kenya"
) -> Dict[str, Any]:
    prompt = f"""Interpret this {jurisdiction} statute{f' section {section}' if section else ''}:
{statute_text[:5000]}
Return ONLY valid JSON:
{{"plain_meaning": str, "legal_meaning": str,
  "case_law": [{{"case": str, "citation": str, "interpretation": str}}],
  "practical_application": str, "exceptions": [str], "recent_developments": str}}"""
    raw = await _call_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k, default in [
            ("plain_meaning", ""), ("legal_meaning", ""), ("case_law", []),
            ("practical_application", ""), ("exceptions", []),
            ("recent_developments", ""),
        ]:
            parsed.setdefault(k, default)
        return parsed
    return {"plain_meaning": "Interpretation unavailable", "legal_meaning": "",
            "case_law": [], "practical_application": "", "exceptions": [],
            "recent_developments": ""}


async def generate_study_plan(
    topic: str, exam_date: str = "", jurisdiction: str = "kenya"
) -> Dict[str, Any]:
    prompt = (
        f"Create a study plan for \"{topic}\" in {jurisdiction} law"
        + (f" for exam on {exam_date}" if exam_date else "")
        + ". Include: week-by-week breakdown, must-know cases with summaries, "
          "key statutes with sections, 5 likely exam questions, study tips, resources."
    )
    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k in ("weekly_plan", "key_cases", "key_statutes", "practice_questions", "resources"):
            parsed.setdefault(k, [] if k != "weekly_plan" else [])
        parsed.setdefault("study_tips", "")
        return parsed
    return {"weekly_plan": [], "key_cases": [], "key_statutes": [],
            "practice_questions": [], "study_tips": "", "resources": []}


async def translate_legal_term(
    term: str,
    source_lang: str = "english",
    target_lang: str = "swahili",
    jurisdiction: str = "kenya",
) -> Dict[str, str]:
    prompt = (
        f'Translate "{term}" from {source_lang} to {target_lang} for {jurisdiction} legal context.\n'
        "Return ONLY valid JSON: "
        '{"original": str, "translation": str, "legal_translation": str,'
        ' "explanation_en": str, "explanation_local": str, "usage": str}'
    )
    raw = await _call_model(prompt, max_tokens=400, temperature=0.3)
    parsed = _json(raw, {})
    if isinstance(parsed, dict):
        for k in ("original", "translation", "legal_translation",
                  "explanation_en", "explanation_local", "usage"):
            parsed.setdefault(k, "")
        parsed.setdefault("original", term)
        return parsed
    return {"original": term, "translation": "Translation unavailable",
            "legal_translation": "", "explanation_en": "", "explanation_local": "", "usage": ""}
