import os
import json
import logging
import re
import httpx
from typing import Any, Dict, List

logger = logging.getLogger("juriscore")

_client = None
_base_url = "https://integrate.api.nvidia.com/v1"
_model = "nvidia/llama-3.1-nemotron-70b-instruct"

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
    global _client
    api_key = os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai
            _client = openai.OpenAI(api_key=api_key, base_url=_base_url)
            logger.info(f"NVIDIA AI client initialized (model: {_model})")
        except Exception as e:
            logger.warning(f"Failed to init AI client: {e}")
            _client = None
    else:
        logger.warning("No NVIDIA_API_KEY set - AI features disabled")
        _client = None


def _call_model(prompt: str, max_tokens: int = 1024, system: str = None) -> str:
    if not _client:
        return ""
    try:
        messages = [
            {"role": "system", "content": system or HUMANIZE_SYSTEM},
            {"role": "user", "content": prompt}
        ]
        resp = _client.chat.completions.create(
            model=_model,
            messages=messages,
            temperature=0.7,
            max_tokens=max_tokens,
            top_p=0.9,
        )
        content = resp.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return content
    except Exception as e:
        logger.error(f"model call failed: {e}")
        return ""


def generate_case_summary(full_text: str) -> Dict[str, Any]:
    prompt = f"""Summarise this Kenyan legal case. Write it the way a sharp law student would explain it to a study group — direct, opinionated, specific.

Return ONLY valid JSON with these keys:
- facts: string (2-3 paragraphs, specific facts, name the parties and what happened)
- issues: list of strings (the legal issues, framed as questions)
- holdings: list of strings (what the court decided, with article/section references)
- ratio: string (the ratio decidendi — the binding principle, cite the case)
- obiter: string (obiter dicta — anything non-binding but interesting)
- cases_cited: list of strings (cite each case properly)

Case text:
{full_text[:6000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        for key in ["facts", "issues", "holdings", "ratio", "obiter", "cases_cited"]:
            parsed.setdefault(key, "" if key in ["facts", "ratio", "obiter"] else [])
        return parsed
    except Exception:
        return {
            "facts": "Summary generation is temporarily unavailable.",
            "issues": [], "holdings": [], "ratio": "", "obiter": "", "cases_cited": []
        }


def generate_study_notes(full_text: str) -> Dict[str, Any]:
    prompt = f"""Create study notes for this case — the kind a top student would make before an exam.

Return ONLY valid JSON with:
- facts: string (concise factual background)
- issues: list (legal issues framed as exam questions)
- holdings: list (court's answers, with authority)
- ratio: string (the rule you'd write on an exam answer)
- key_quotes: list of exact quotes from the judgment (max 5, max 40 words each)
- annotations: list of short study annotations

Case text:
{full_text[:6000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        for key in ["facts", "issues", "holdings", "ratio", "key_quotes", "annotations"]:
            parsed.setdefault(key, "" if key == "facts" or key == "ratio" else [])
        return parsed
    except Exception:
        return {"facts": "", "issues": [], "holdings": [], "ratio": "", "key_quotes": [], "annotations": []}


def generate_citation(case_data: Dict) -> Dict[str, str]:
    prompt = f"""Format this case data into a proper Kenyan eKLR citation. Be precise.

Return ONLY valid JSON with: parties, year, court, neutral_citation, formatted.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        for key in ["parties", "year", "court", "neutral_citation", "formatted"]:
            parsed.setdefault(key, "")
        return parsed
    except Exception:
        return {"parties": "", "year": "", "court": "", "neutral_citation": "", "formatted": ""}


def compare_cases(case_a_text: str, case_b_text: str) -> Dict[str, Any]:
    prompt = f"""Compare these two Kenyan cases. Don't just list similarities — actually analyse whether they're consistent, distinguishable, or in tension.

Return ONLY valid JSON with: similarities, differences, legal_proposition_a, legal_proposition_b, recommendation.

Case A:
{case_a_text[:4000]}

Case B:
{case_b_text[:4000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        for key in ["similarities", "differences", "legal_proposition_a", "legal_proposition_b", "recommendation"]:
            parsed.setdefault(key, [])
        return parsed
    except Exception:
        return {"similarities": [], "differences": [], "legal_proposition_a": "", "legal_proposition_b": "", "recommendation": ""}


def generate_flashcard(case_data: Dict) -> Dict[str, str]:
    prompt = f"""From this case, create ONE flashcard that would actually help during exam revision.

front = a specific question about the holding, ratio, or a key fact (max 20 words)
back = concise answer with the case name and principle (max 60 words)

Return ONLY valid JSON with keys front and back.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        parsed.setdefault("front", "What is the holding?")
        parsed.setdefault("back", "TBD")
        return parsed
    except Exception:
        return {"front": "What is the holding?", "back": "TBD"}


def generate_summary_from_metadata(title: str, citation: str, court: str, date: str, doc_type: str, excerpt: str = "") -> str:
    """Generate a natural-language summary from search result metadata.
    Used when the user clicks 'Summarize' on a search result."""
    prompt = f"""Write a clear, useful summary of this Kenyan legal document for a law student.

Write like a knowledgeable peer explaining this — not like a database entry. Be specific about what this document is, why it matters, and what a student should know about it.

Document details:
- Title: {title}
- Citation: {citation}
- Court: {court}
- Date: {date}
- Type: {doc_type}
- Excerpt: {excerpt}

Write 2-3 paragraphs. Be direct. Name specific legal principles. If it's a case, state the ratio. If it's legislation, state what it regulates. Don't use AI words like "delve", "comprehensive", or "in conclusion"."""

    result = _call_model(prompt, max_tokens=800)
    return result if result else f"Summary unavailable for: {title}"


def extract_key_quotes(text: str, max_quotes: int = 5) -> List[str]:
    prompt = f"""Extract up to {max_quotes} key legal quotes from this text. Pick the ones a student would highlight for an exam.

Return ONLY a JSON array of strings (max 40 words each).

{text[:6000]}

JSON:"""
    raw = _call_model(prompt, max_tokens=512)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed[:max_quotes]
        return []
    except Exception:
        return []


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
