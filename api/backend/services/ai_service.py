import os
import json
import logging
import re
import httpx
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger("juriscore")

# API Configuration - Dual model architecture
# Fast model (NVIDIA): Quick responses, search, flashcards, simple queries
# Reasoning model (Mistral): Complex analysis, summaries, legal memos, study notes

class AIProvider(Enum):
    NVIDIA = "nvidia"
    MISTRAL = "mistral"
    OPENAI = "openai"

# Primary (fast) model config
_api_key = ""
_provider = None
_base_url = ""
_model = ""

# Secondary (reasoning) model config
_reasoning_key = ""
_reasoning_provider = None
_reasoning_base_url = ""
_reasoning_model = ""

# NVIDIA - Fast model for general queries
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_FAST_MODEL = "nvidia/llama-3.1-nemotron-70b-instruct"

# Mistral - Reasoning model for complex tasks
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
MISTRAL_REASONING_MODEL = "mistral-large-latest"

# OpenAI fallback
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"

HUMANIZE_SYSTEM = """You are a senior Kenyan legal scholar who writes with genuine authority and a distinct voice. You write like a real person who has spent years in courtrooms and libraries — not like a language model.

CRITICAL WRITING RULES:
- VARY sentence length dramatically. Mix 4-word punchy sentences with 30-word complex ones. Never let 4 consecutive sentences be similar length.
- NEVER use these words: delve, furthermore, moreover, utilize, leverage, robust, pivotal, paramount, comprehensive, seamless, holistic, tapestry, journey, game-changer, groundbreaking, nuanced, multifaceted.
- NEVER start paragraphs with: "Furthermore", "Moreover", "In addition", "It is important to note", "Having said that".
- NEVER end with: "In conclusion", "As we have seen", "To sum up".
- COMMIT to positions. Say "the court got this wrong" not "it may be questioned".
- Be SPECIFIC. Name cases, dates, numbers, judges. Not "recent developments" but "the March 2026 ruling in Republic v Odaha".
- USE contractions naturally: don't, can't, it's, they've — especially in asides and concessions.
- PUNCTUATION: Use em dashes (—), semicolons (;), parenthetical asides, rhetorical questions.
- Write with temperature: firm when arguing, puzzled when describing complexity, grudging when conceding.
- One deliberate imperfection per section: a fragment, starting with "But" or "So", a short sentence after a long one.
- For Kenyan law: cite using standard format — Case Name [Year] KEHC/KECA number (KLR). Reference the Constitution of Kenya 2010 by article number."""


def init_backend():
    """Initialize AI backend with dual-model architecture.
    Fast model (NVIDIA) for general queries, reasoning model (Mistral) for complex tasks.
    """
    global _api_key, _provider, _base_url, _model
    global _reasoning_key, _reasoning_provider, _reasoning_base_url, _reasoning_model

    # --- Fast model: NVIDIA ---
    nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip()
    if nvidia_key:
        _api_key = nvidia_key
        _provider = AIProvider.NVIDIA
        _base_url = NVIDIA_BASE_URL
        _model = NVIDIA_FAST_MODEL
        logger.info(f"Fast model initialized: NVIDIA ({_model})")

    # --- Reasoning model: Mistral ---
    mistral_key = os.getenv("MISTRAL_API_KEY", "").strip()
    if mistral_key:
        _reasoning_key = mistral_key
        _reasoning_provider = AIProvider.MISTRAL
        _reasoning_base_url = MISTRAL_BASE_URL
        _reasoning_model = MISTRAL_REASONING_MODEL
        logger.info(f"Reasoning model initialized: Mistral ({_reasoning_model})")

    # Fallback: if no fast model but reasoning exists, use reasoning as primary
    if not _api_key and _reasoning_key:
        _api_key = _reasoning_key
        _provider = _reasoning_provider
        _base_url = _reasoning_base_url
        _model = _reasoning_model
        logger.info("Using Mistral as primary (no NVIDIA key)")

    # Fallback: OpenAI
    if not _api_key:
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if openai_key:
            _api_key = openai_key
            _provider = AIProvider.OPENAI
            _base_url = OPENAI_BASE_URL
            _model = OPENAI_MODEL
            logger.info(f"Fallback to OpenAI ({_model})")

    if not _api_key:
        logger.error("No API keys configured! Set NVIDIA_API_KEY or MISTRAL_API_KEY")
        _provider = None


def _is_configured() -> bool:
    """Check if AI service is properly configured."""
    return _api_key and _provider is not None


async def _call_model(prompt: str, max_tokens: int = 1024, system: str = None, temperature: float = 0.7) -> str:
    """Call the FAST model (NVIDIA) with retry logic."""
    return await _call_provider(prompt, max_tokens=max_tokens, system=system, temperature=temperature,
                                key=_api_key, provider=_provider, base_url=_base_url, model=_model)


async def _call_reasoning_model(prompt: str, max_tokens: int = 2048, system: str = None, temperature: float = 0.5) -> str:
    """Call the REASONING model (Mistral) for complex tasks."""
    if _reasoning_key and _reasoning_provider:
        return await _call_provider(prompt, max_tokens=max_tokens, system=system, temperature=temperature,
                                    key=_reasoning_key, provider=_reasoning_provider, base_url=_reasoning_base_url, model=_reasoning_model)
    # Fallback to fast model if reasoning not configured
    return await _call_model(prompt, max_tokens=max_tokens, system=system, temperature=temperature)


async def _call_provider(prompt: str, max_tokens: int, system: str, temperature: float,
                         key: str, provider, base_url: str, model: str) -> str:
    """Low-level provider call with retry logic."""
    if not key or not provider:
        return ""

    messages = [
        {"role": "system", "content": system or HUMANIZE_SYSTEM},
        {"role": "user", "content": prompt}
    ]

    if provider == AIProvider.NVIDIA:
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens, "top_p": 0.9}
        endpoint = f"{base_url}/chat/completions"
    elif provider == AIProvider.MISTRAL:
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        endpoint = f"{base_url}/chat/completions"
    elif provider == AIProvider.OPENAI:
        payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        endpoint = f"{base_url}/chat/completions"
    else:
        return ""

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    max_retries = 3
    import asyncio
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(endpoint, json=payload, headers=headers)

                if resp.status_code == 429:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1 * (2 ** attempt))
                        continue
                    return ""

                resp.raise_for_status()
                data = resp.json()

                if "choices" not in data or not data["choices"]:
                    return ""

                content = data["choices"][0]["message"]["content"].strip()
                content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL).strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)

                if content and len(content) > 10:
                    return content
                return ""

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (2 ** attempt))
                continue
            return ""
        except httpx.HTTPStatusError as e:
            if e.response.status_code in [401, 403]:
                return ""
            if attempt < max_retries - 1 and e.response.status_code >= 500:
                await asyncio.sleep(1 * (2 ** attempt))
                continue
            return ""
        except Exception:
            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (2 ** attempt))
                continue
            return ""

    return ""


def _parse_json(text: str, fallback: Any = None) -> Any:
    """Safely parse JSON from model output."""
    if not text or not isinstance(text, str):
        return fallback
    
    text = text.strip()
    
    # Try multiple parsing approaches
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        # Try finding JSON object in text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        
        logger.warning(f"Failed to parse JSON, using fallback. Text: {text[:100]}")
        return fallback


# ---------- Case Summary ----------

async def generate_case_summary(full_text: str) -> Dict[str, Any]:
    """Generate a structured case summary using IRAC method."""
    if not full_text or len(full_text.strip()) < 50:
        return {
            "facts": "Insufficient case text provided",
            "issues": [],
            "rule": "",
            "application": "",
            "conclusion": "",
            "ratio": "",
            "obiter": "",
            "cases_cited": [],
            "significance": ""
        }
    
    prompt = f"""Analyse this Kenyan legal case using the IRAC method (Issue, Rule, Application, Conclusion). Write like a senior law tutor breaking down a case for a student preparing for exams — precise, authoritative, specific.

Return ONLY valid JSON with these keys:
- facts: string (2-3 paragraphs. Name the parties, the court, the date, the key facts. Be specific — dates, amounts, names, sections cited.)
- issues: list of strings (the legal issues framed as questions the court had to answer)
- rule: string (the applicable legal rules — constitutional provisions, statutory sections, precedent cases cited)
- application: string (how the court applied the rules to the facts — the reasoning chain. This is the most important part.)
- conclusion: string (the court's final decision and order)
- ratio: string (the ratio decidendi — the binding legal principle from this case, cite it properly)
- obiter: string (obiter dicta — persuasive but non-binding observations)
- cases_cited: list of strings (each case properly cited)
- significance: string (why this case matters for Kenyan law)

Case text:
{full_text[:6000]}

JSON:"""
    raw = await _call_reasoning_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})

    if isinstance(parsed, dict) and len(parsed) > 0:
        # Ensure all required keys exist
        for key in ["facts", "issues", "rule", "application", "conclusion", "ratio", "obiter", "cases_cited", "significance"]:
            if key not in parsed:
                parsed[key] = "" if key in ["facts", "rule", "application", "conclusion", "ratio", "obiter", "significance"] else []
        return parsed

    # Fallback when API fails or returns invalid JSON
    logger.warning("Case summary generation failed, returning placeholder")
    return {
        "facts": "AI summary service temporarily unavailable. Please try again in a few moments.",
        "issues": ["Unable to identify issues at this time"],
        "rule": "AI service error - please refresh and try again",
        "application": "Service error",
        "conclusion": "Service error",
        "ratio": "Service error - check your internet connection and try again",
        "obiter": "",
        "cases_cited": [],
        "significance": "Service is experiencing temporary issues"
    }


# ---------- Study Notes ----------

async def generate_study_notes(full_text: str) -> Dict[str, Any]:
    """Generate exam-ready study notes."""
    if not full_text or len(full_text.strip()) < 50:
        return {
            "facts": "Insufficient case text",
            "issues": [],
            "rule": "",
            "application": "",
            "conclusion": "",
            "ratio": "",
            "key_quotes": [],
            "significance": ""
        }
    
    prompt = f"""Create exam-ready study notes for this case using the IRAC method. Write like a top student's personal case brief.

Return ONLY valid JSON with:
- facts: string (concise factual background)
- issues: list (legal issues framed as exam questions)
- rule: string (applicable legal rules and statutes)
- application: string (how the court applied the rules)
- conclusion: string (the court's final decision)
- ratio: string (the ratio decidendi)
- key_quotes: list of exact quotes (max 5, max 40 words each)
- significance: string (why this case matters)

Case text:
{full_text[:6000]}

JSON:"""
    raw = await _call_reasoning_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict) and len(parsed) > 0:
        for key in ["facts", "issues", "rule", "application", "conclusion", "ratio", "key_quotes", "significance"]:
            if key not in parsed:
                parsed[key] = "" if key in ["facts", "rule", "application", "conclusion", "ratio", "significance"] else []
        return parsed
    
    return {
        "facts": "Study notes unavailable - AI service error",
        "issues": [],
        "rule": "Please try again in a moment",
        "application": "",
        "conclusion": "",
        "ratio": "",
        "key_quotes": [],
        "significance": ""
    }


# ---------- Citation ----------

async def generate_citation(case_data: Dict) -> Dict[str, str]:
    """Generate proper Kenyan eKLR citation."""
    if not case_data:
        return {
            "parties": "Unknown",
            "year": "",
            "court": "",
            "neutral_citation": "",
            "formatted": "Citation data unavailable"
        }
    
    prompt = f"""Format this case data into a proper Kenyan eKLR citation.

Case data:
{json.dumps(case_data)[:2000]}

Return ONLY valid JSON with: parties, year, court, neutral_citation, formatted.

Example format: "Smith v. State [2023] KEHC 123 (KLR)"

JSON:"""
    raw = await _call_model(prompt, temperature=0.3)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict) and len(parsed) > 0:
        for key in ["parties", "year", "court", "neutral_citation", "formatted"]:
            parsed.setdefault(key, "")
        return parsed
    
    # Fallback formatting
    parties = case_data.get("title", "Unknown case")
    year = case_data.get("year", "")
    court = case_data.get("court", "")
    return {
        "parties": parties,
        "year": str(year),
        "court": court,
        "neutral_citation": "",
        "formatted": f"{parties} ({year})"
    }


# ---------- Case Comparison ----------

async def compare_cases(case_a_text: str, case_b_text: str) -> Dict[str, Any]:
    """Compare two Kenyan cases and analyse consistency."""
    if not case_a_text or not case_b_text:
        return {
            "similarities": ["Insufficient data provided"],
            "differences": ["Cannot compare - missing case text"],
            "legal_proposition_a": "",
            "legal_proposition_b": "",
            "recommendation": "Please provide full case texts"
        }
    
    prompt = f"""Compare these two Kenyan cases. Analyse whether they're consistent, distinguishable, or in tension.

Return ONLY valid JSON with: similarities, differences, legal_proposition_a, legal_proposition_b, recommendation.

Case A:
{case_a_text[:4000]}

Case B:
{case_b_text[:4000]}

JSON:"""
    raw = await _call_reasoning_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict) and len(parsed) > 0:
        for key in ["similarities", "differences", "legal_proposition_a", "legal_proposition_b", "recommendation"]:
            if key not in parsed:
                parsed[key] = [] if key in ["similarities", "differences"] else ""
        return parsed
    
    return {
        "similarities": ["Cannot compare - AI service error"],
        "differences": [],
        "legal_proposition_a": "",
        "legal_proposition_b": "",
        "recommendation": "Please try again later"
    }


# ---------- Flashcard ----------

async def generate_flashcard(case_data: Dict) -> Dict[str, str]:
    """Generate a study flashcard from case data."""
    if not case_data:
        return {
            "front": "What legal principle is this case about?",
            "back": "Unable to generate flashcard - no data provided"
        }
    
    prompt = f"""From this case, create ONE flashcard for exam revision.

front = a specific question about the holding, ratio, or a key fact (max 20 words)
back = concise answer with the case name and principle (max 60 words)

Return ONLY valid JSON with keys front and back.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict) and len(parsed) > 0:
        parsed.setdefault("front", "What is the holding?")
        parsed.setdefault("back", "TBD")
        return parsed
    
    return {
        "front": "What is the key legal principle?",
        "back": "Flashcard generation failed - please try again"
    }


# ---------- Summary from Metadata ----------

async def generate_summary_from_metadata(title: str, citation: str, court: str, date: str, doc_type: str, excerpt: str = "") -> str:
    """Generate a natural-language summary from search result metadata."""
    if not title:
        return "Summary unavailable - document information incomplete"
    
    prompt = f"""Analyse this Kenyan legal document. Write 3-4 paragraphs analyzing the ISSUE, RULE, APPLICATION, and CONCLUSION.

Document:
- Title: {title}
- Citation: {citation}
- Court: {court}
- Date: {date}
- Type: {doc_type}
- Excerpt: {excerpt}

Write in plain text, no markdown. Be specific and authoritative."""

    result = await _call_model(prompt, max_tokens=800, temperature=0.6)
    return result if result and len(result) > 20 else f"Summary unavailable for: {title}. Please check back later."


# ---------- Key Quotes ----------

async def extract_key_quotes(text: str, max_quotes: int = 5) -> List[str]:
    """Extract key legal quotes from text."""
    if not text or len(text.strip()) < 100:
        return ["Insufficient text to extract quotes"]
    
    prompt = f"""Extract up to {max_quotes} key legal quotes from this text. Pick ones a student would highlight.

Return ONLY a JSON array of strings (max 40 words each).

{text[:6000]}

JSON:"""
    raw = await _call_model(prompt, max_tokens=512, temperature=0.4)
    parsed = _parse_json(raw, [])
    if isinstance(parsed, list) and len(parsed) > 0:
        return parsed[:max_quotes]
    return ["Quotes extraction failed - service error"]


# ---------- AI Search ----------

QUERY_REWRITE_SYSTEM = """You are an expert legal search assistant specializing in Kenyan law and the KenyaLaw.org database.

Your task: take a user's search query and produce an improved search query that will find the best results from KenyaLaw.org.

THINK STEP BY STEP:
1. Identify what the user is actually looking for
2. Fix misspellings and typos
3. Expand abbreviations
4. Add legal context where needed

Return ONLY valid JSON: {"query": "improved query", "suggestions": ["alt1", "alt2"], "reasoning": "explanation"}"""


async def rewrite_search_query(query: str) -> Dict[str, Any]:
    """Use AI to correct and improve search queries."""
    if not query or len(query.strip()) < 2:
        return {"query": query, "suggestions": [], "corrected": False}
    
    if not _is_configured():
        logger.warning("AI search rewrite disabled - no API configured")
        return {"query": query, "suggestions": [], "corrected": False}

    prompt = f"""Improve this legal search query for KenyaLaw.org database.

User query: "{query}"

Think: What is the user looking for? Are there misspellings? What abbreviations need expanding?

Return JSON: {{"query": "corrected", "suggestions": ["alt1", "alt2"], "reasoning": "why changed"}}"""

    try:
        raw = await _call_model(prompt, max_tokens=300, system=QUERY_REWRITE_SYSTEM, temperature=0.3)
        parsed = _parse_json(raw, {})
        if isinstance(parsed, dict):
            corrected_query = parsed.get("query", query).strip()
            suggestions = parsed.get("suggestions", [])
            corrected = corrected_query.lower().replace(" ", "") != query.lower().replace(" ", "")
            return {"query": corrected_query, "suggestions": suggestions[:3], "corrected": corrected}
    except Exception as e:
        logger.error(f"Search query rewrite failed: {e}")
    
    return {"query": query, "suggestions": [], "corrected": False}


RANK_SYSTEM = """You are a legal research expert specializing in Kenyan law. Rank search results by relevance to the user's query."""


async def rank_search_results(query: str, results: List[Dict], top_n: int = 30) -> List[Dict]:
    """Use AI to re-rank search results by relevance."""
    if not query or not results:
        return results
    
    if not _is_configured():
        logger.debug("AI ranking disabled - returning original order")
        return results[:top_n]
    
    if len(results) <= 5:
        logger.debug(f"Few results ({len(results)}), skipping AI ranking")
        return results
    
    try:
        listing = "\n".join(
            f"[{i}] {r.get('title', 'Untitled')} | Court: {r.get('court', 'N/A')} | Type: {r.get('doc_type', 'N/A')}"
            for i, r in enumerate(results[:100])  # Limit input size
        )

        prompt = f"""Rank these results by relevance to: "{query}"

Results:
{listing}

Return ONLY JSON array of indices (most relevant first): [0, 5, 2]"""

        raw = await _call_model(prompt, max_tokens=500, system=RANK_SYSTEM, temperature=0.3)
        parsed = _parse_json(raw, [])
        if isinstance(parsed, list):
            ranked = []
            seen = set()
            for idx in parsed:
                if isinstance(idx, int) and 0 <= idx < len(results) and idx not in seen:
                    ranked.append(results[idx])
                    seen.add(idx)
            for i, r in enumerate(results):
                if i not in seen:
                    ranked.append(r)
            return ranked[:top_n]
    except Exception as e:
        logger.error(f"Search ranking failed: {e}")
    
    return results[:top_n]


# ---------- Fuzzy Matching ----------

def fuzzy_match_term(term: str, candidates: List[str], threshold: float = 0.5) -> Optional[str]:
    """Find the closest matching term from a list of candidates."""
    from difflib import SequenceMatcher
    term_lower = term.lower().strip()
    best_match = None
    best_score = 0.0

    for candidate in candidates:
        candidate_lower = candidate.lower().strip()
        if term_lower == candidate_lower:
            return candidate
        if term_lower in candidate_lower or candidate_lower in term_lower:
            score = 0.9
        else:
            score = SequenceMatcher(None, term_lower, candidate_lower).ratio()
            term_words = set(term_lower.split())
            cand_words = set(candidate_lower.split())
            if term_words & cand_words:
                score = max(score, 0.75)
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_score >= threshold:
        return best_match
    return None


KNOWN_COURTS = [
    "Supreme Court", "Court of Appeal", "High Court",
    "Environment and Land Court", "Employment and Labour Relations Court",
    "Magistrate Court", "Kadhi Court", "Military Court",
    "Tribunal", "Industrial Court", "Commercial Court",
    "Constitutional Court", "Family Court", "Criminal Division",
    "Civil Division", "Judicial Review Division", "Anti-Corruption Court",
    "Drug Traffic Court", "Tax Tribunal", "Nairobi", "Mombasa",
    "Kisumu", "Nakuru", "Eldoret", "Nyeri", "Machakos", "Meru",
]

KNOWN_DOC_TYPES = [
    "judgment", "legislation", "gazette", "bill",
    "generic_document", "journal", "causelist",
    "case law", "act", "regulation", "statute",
]


def fuzzy_match_court(court_input: str) -> Optional[str]:
    return fuzzy_match_term(court_input, KNOWN_COURTS, threshold=0.45)


def fuzzy_match_doc_type(type_input: str) -> Optional[str]:
    aliases = {
        "case": "judgment", "cases": "judgment", "case law": "judgment",
        "law": "legislation", "act": "legislation", "acts": "legislation",
        "statute": "legislation", "statutes": "legislation",
        "gazette": "gazette", "gazettes": "gazette",
        "bill": "bill", "bills": "bill",
        "publication": "generic_document", "publications": "generic_document",
        "journal": "journal", "journals": "journal",
        "cause list": "causelist", "causelists": "causelist",
    }
    lower = type_input.lower().strip()
    if lower in aliases:
        return aliases[lower]
    return fuzzy_match_term(lower, KNOWN_DOC_TYPES, threshold=0.45)


def search_similar(query: str, cases: List[Dict]) -> List[str]:
    scored = []
    q_terms = set(re.findall(r"\w+", query.lower()))
    for c in cases:
        text = " ".join([c.get("title", ""), c.get("full_text", "")]).lower()
        terms = set(re.findall(r"\w+", text))
        score = len(q_terms & terms)
        scored.append((score, c.get("id", "")))
    scored.sort(reverse=True)
    return [cid for _, cid in scored]


# ==================== COMPREHENSIVE AI TOOLS ====================

LEGAL_RESEARCH_SYSTEM = """You are a world-class legal research assistant with expertise across multiple jurisdictions and legal systems. You have deep knowledge of:
- Common law, civil law, religious law, and mixed legal systems
- International law, human rights law, trade law, environmental law
- African legal systems (East African, ECOWAS, SADC, African Union)
- Major world legal systems (US, UK, EU, India, Australia, Canada, etc.)

You provide precise, well-cited legal analysis. Always cite specific cases, statutes, or articles when making legal points."""


async def legal_research_assistant(query: str, jurisdiction: str = "kenya") -> Dict[str, Any]:
    """Comprehensive legal research across multiple jurisdictions."""
    prompt = f"""Provide comprehensive legal research on this query for {jurisdiction} jurisdiction:

Query: "{query}"

Provide:
1. Legal framework: What laws/acts/constitution articles apply
2. Key cases: Relevant case law with citations
3. Legal principles: Established legal principles that apply
4. Practical implications: What this means in practice
5. Related topics: Related legal areas to explore

Be specific with citations. Format as JSON:
{{
    "legal_framework": "description of applicable laws",
    "key_cases": [{{"name": "Case Name", "citation": "[Year] eKLR", "principle": "what it established"}}],
    "legal_principles": ["principle 1", "principle 2"],
    "practical_implications": "what this means",
    "related_topics": ["topic 1", "topic 2"]
}}"""

    raw = await _call_reasoning_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {
        "legal_framework": "Research temporarily unavailable",
        "key_cases": [],
        "legal_principles": [],
        "practical_implications": "",
        "related_topics": []
    }


async def format_citation(case_data: Dict, jurisdiction: str = "kenya") -> str:
    """Format citation according to jurisdiction-specific rules."""
    citation_rules = {
        "kenya": "Case Name [Year] eKLR (Kenya Law Reports)",
        "nigeria": "Case Name [Year] LPELR-XXXX (Nigerian Law Reports)",
        "south_africa": "Case Name [Year] ZACC/ZZA/ZZG (South African Constitutional Court)",
        "uk": "Case Name [Year] UKSC/UKHL/EWCA/Civil/Criminal (Law Reports)",
        "us": "Case Name Volume Reporter Page (Court Year)",
        "india": "Case Name (Year) SCC (Supreme Court Cases)",
        "international": "Case Name [Year] ICJ/ECtHR/AfCHPR Reports",
    }

    prompt = f"""Format this case citation according to {jurisdiction} citation rules.

Case data:
- Title: {case_data.get('title', 'Unknown')}
- Court: {case_data.get('court', 'Unknown')}
- Year: {case_data.get('year', 'Unknown')}
- Citation: {case_data.get('citation', 'Unknown')}

Citation format: {citation_rules.get(jurisdiction, citation_rules['kenya'])}

Return ONLY the properly formatted citation string."""

    result = await _call_model(prompt, max_tokens=200, temperature=0.2)
    return result if result else f"{case_data.get('title', 'Unknown')} [{case_data.get('year', 'Year')}] {jurisdiction.title()} Reports"


async def explain_legal_concept(concept: str, jurisdiction: str = "kenya") -> str:
    """Explain a legal concept with jurisdiction-specific context."""
    prompt = f"""Explain this legal concept clearly and concisely for a law student in {jurisdiction}:

"{concept}"

Provide:
1. Definition in plain language
2. How it applies in {jurisdiction}
3. Key cases that established/defined it
4. Common exam questions about it
5. Practical examples

Write like a knowledgeable tutor — direct, specific, with real examples."""

    result = await _call_reasoning_model(prompt, max_tokens=800, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    return result if result else f"Explanation unavailable for: {concept}"


async def compare_jurisdictions(
    legal_issue: str,
    jurisdictions: List[str] = None,
) -> Dict[str, Any]:
    """Compare how different jurisdictions handle the same legal issue."""
    if not jurisdictions:
        jurisdictions = ["kenya", "nigeria", "south_africa", "uk", "us"]

    prompt = f"""Compare how these jurisdictions handle the legal issue: "{legal_issue}"

Jurisdictions: {', '.join(jurisdictions)}

For each jurisdiction, explain:
1. The applicable law/constitution
2. How courts have interpreted it
3. Key differences from other jurisdictions
4. Trends or developments

Format as JSON:
{{
    "issue": "{legal_issue}",
    "comparisons": {{
        "kenya": {{"law": "...", "interpretation": "...", "key_cases": ["..."], "unique_aspect": "..."}},
        "nigeria": {{"law": "...", "interpretation": "...", "key_cases": ["..."], "unique_aspect": "..."}},
        ...
    }},
    "key_differences": ["difference 1", "difference 2"],
    "trend": "description of global trend"
}}"""

    raw = await _call_reasoning_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {"issue": legal_issue, "comparisons": {}, "key_differences": [], "trend": ""}


async def generate_legal_memo(
    issue: str,
    facts: str = "",
    jurisdiction: str = "kenya",
) -> str:
    """Generate a legal memorandum analyzing a legal issue."""
    prompt = f"""Write a legal memorandum analyzing this issue for {jurisdiction}:

Issue: {issue}
{"Facts: " + facts if facts else ""}

Structure:
1. ISSUE(S) PRESENTED
2. BRIEF ANSWER
3. STATEMENT OF FACTS (if provided)
4. DISCUSSION
   - Applicable law
   - Case law analysis
   - Application to facts
5. CONCLUSION

Be direct. Cite specific cases and statutes. Write like a practicing lawyer, not a textbook."""

    result = await _call_reasoning_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    return result if result else f"Legal memo generation unavailable for: {issue}"


async def analyze_case_law(case_text: str, jurisdiction: str = "kenya") -> Dict[str, Any]:
    """Deep analysis of case law with cross-jurisdictional comparison."""
    prompt = f"""Provide deep analysis of this {jurisdiction} case:

Case text:
{case_text[:5000]}

Analyze:
1. FACTS: Detailed factual summary
2. ISSUES: All legal issues (framed as questions)
3. HOLDINGS: Each holding with article/section references
4. RATIO: The ratio decidendi (binding principle)
5. OBITER: Notable obiter dicta
6. SIGNIFICANCE: Why this case matters
7. CRITIQUE: Any controversial aspects or criticisms
8. APPLICATION: How this applies to similar facts
9. RELATED CASES: Similar cases in other jurisdictions
10. EXAM RELEVANCE: Likely exam questions

Format as JSON with these keys."""

    raw = await _call_reasoning_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {
        "facts": "", "issues": [], "holdings": [], "ratio": "",
        "obiter": "", "significance": "", "critique": "",
        "application": "", "related_cases": [], "exam_relevance": []
    }


async def interpret_statute(
    statute_text: str,
    section: str = "",
    jurisdiction: str = "kenya",
) -> Dict[str, Any]:
    """Interplain a statute section with case law context."""
    prompt = f"""Interpret this {jurisdiction} statute{(' section ' + section) if section else ''}:

Statute text:
{statute_text[:5000]}

Provide:
1. Plain meaning: What the words say
2. Legal meaning: How courts interpret it
3. Case law: Key cases interpreting this provision
4. Practical application: How it works in practice
5. Exceptions/limitations: Any exceptions or limitations
6. Recent developments: Any recent changes or interpretations

Format as JSON:
{{
    "plain_meaning": "...",
    "legal_meaning": "...",
    "case_law": [{{"case": "Name", "citation": "...", "interpretation": "..."}}],
    "practical_application": "...",
    "exceptions": ["..."],
    "recent_developments": "..."
}}"""

    raw = await _call_reasoning_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {
        "plain_meaning": "Interpretation unavailable",
        "legal_meaning": "",
        "case_law": [],
        "practical_application": "",
        "exceptions": [],
        "recent_developments": ""
    }


async def generate_study_plan(
    topic: str,
    exam_date: str = "",
    jurisdiction: str = "kenya",
) -> Dict[str, Any]:
    """Generate a personalized study plan for a legal topic."""
    prompt = f"""Create a study plan for mastering "{topic}" in {jurisdiction} law{"for an exam on " + exam_date if exam_date else ""}.

Include:
1. WEEK-BY-WEEK BREAKDOWN: Topics to cover each week
2. KEY CASES: Must-know cases with brief summaries
3. KEY STATUTES: Important acts and sections
4. PRACTICE QUESTIONS: 5 likely exam questions
5. STUDY TIPS: How to approach this topic
6. RESOURCES: Where to find more information

Make it practical and achievable. Focus on what's most likely to be examined."""

    raw = await _call_reasoning_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {
        "weekly_plan": [],
        "key_cases": [],
        "key_statutes": [],
        "practice_questions": [],
        "study_tips": "",
        "resources": []
    }


async def translate_legal_term(
    term: str,
    source_lang: str = "english",
    target_lang: str = "swahili",
    jurisdiction: str = "kenya",
) -> Dict[str, str]:
    """Translate legal terms with jurisdiction-specific context."""
    prompt = f"""Translate this legal term from {source_lang} to {target_lang} for {jurisdiction} legal context:

"{term}"

Provide:
1. Direct translation
2. Legal translation (if different)
3. Explanation of the concept in both languages
4. Usage in legal documents

Format as JSON:
{{
    "original": "{term}",
    "translation": "...",
    "legal_translation": "...",
    "explanation_en": "...",
    "explanation_local": "...",
    "usage": "..."
}}"""

    raw = await _call_model(prompt, max_tokens=400, temperature=0.3)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        return parsed
    return {
        "original": term,
        "translation": "Translation unavailable",
        "legal_translation": "",
        "explanation_en": "",
        "explanation_local": "",
        "usage": ""
    }
