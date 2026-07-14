import os
import json
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger("juriscore")

_client = None


def init_backend():
    global _client
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai
            _client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized")
        except Exception as e:
            logger.warning(f"Failed to init OpenAI: {e}")
            _client = None
    else:
        logger.warning("No OPENAI_API_KEY set - AI features disabled")
        _client = None


def _call_model(prompt: str, max_tokens: int = 512) -> str:
    if not _client:
        return ""
    try:
        resp = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"model call failed: {e}")
        return ""


def generate_case_summary(full_text: str) -> Dict[str, Any]:
    prompt = f"""You are a legal research assistant. From the following Kenyan legal case text, produce a structured JSON with keys: facts, issues, holdings, ratio, obiter, cases_cited. Return ONLY valid JSON, no markdown, no commentary.

Case text:
{full_text[:8000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        parsed.setdefault("facts", "")
        parsed.setdefault("issues", [])
        parsed.setdefault("holdings", [])
        parsed.setdefault("ratio", "")
        parsed.setdefault("obiter", "")
        parsed.setdefault("cases_cited", [])
        return parsed
    except Exception:
        return {"facts": "", "issues": [], "holdings": [], "ratio": "", "obiter": "", "cases_cited": []}


def generate_study_notes(full_text: str) -> Dict[str, Any]:
    prompt = f"""You are a legal study assistant. Based on the following case text, produce a structured JSON with keys: facts, issues, holdings, ratio, key_quotes, annotations. key_quotes must be a list of exact quotes from the text (max 5). annotations is a list of short annotation strings. Return ONLY valid JSON.

Case text:
{full_text[:8000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        parsed.setdefault("facts", "")
        parsed.setdefault("issues", [])
        parsed.setdefault("holdings", [])
        parsed.setdefault("ratio", "")
        parsed.setdefault("key_quotes", [])
        parsed.setdefault("annotations", [])
        return parsed
    except Exception:
        return {"facts": "", "issues": [], "holdings": [], "ratio": "", "key_quotes": [], "annotations": []}


def generate_citation(case_data: Dict) -> Dict[str, str]:
    prompt = f"""From the following case metadata, produce a structured eKLR citation object with keys: parties, year, court, neutral_citation, formatted. Return ONLY valid JSON.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        parsed.setdefault("parties", "")
        parsed.setdefault("year", "")
        parsed.setdefault("court", "")
        parsed.setdefault("neutral_citation", "")
        parsed.setdefault("formatted", "")
        return parsed
    except Exception:
        return {"parties": "", "year": "", "court": "", "neutral_citation": "", "formatted": ""}


def compare_cases(case_a_text: str, case_b_text: str) -> Dict[str, Any]:
    prompt = f"""Compare these two Kenyan legal cases and return a structured JSON object with keys: similarities, differences, legal_proposition_a, legal_proposition_b, recommendation. Keep it factual and concise. Return ONLY valid JSON.

Case A:
{case_a_text[:4000]}

Case B:
{case_b_text[:4000]}

JSON:"""
    raw = _call_model(prompt)
    try:
        parsed = json.loads(raw)
        parsed.setdefault("similarities", [])
        parsed.setdefault("differences", [])
        parsed.setdefault("legal_proposition_a", "")
        parsed.setdefault("legal_proposition_b", "")
        parsed.setdefault("recommendation", "")
        return parsed
    except Exception:
        return {"similarities": [], "differences": [], "legal_proposition_a": "", "legal_proposition_b": "", "recommendation": ""}


def generate_flashcard(case_data: Dict) -> Dict[str, str]:
    prompt = f"""From the following case metadata, generate ONE flashcard in JSON format with keys front and back. front should be a short prompt (max 20 words). back should be a concise answer (max 60 words). Return ONLY valid JSON.

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


def extract_key_quotes(text: str, max_quotes: int = 5) -> List[str]:
    prompt = f"""Extract up to {max_quotes} key legal quotes from the following text as a JSON array of strings (max 40 words each). Return ONLY valid JSON.

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
