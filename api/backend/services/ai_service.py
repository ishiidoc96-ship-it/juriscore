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

# Free fast models on NVIDIA:
# nvidia/llama-3.1-nemotron-70b-instruct  (fast, good reasoning)
# meta/llama-3.3-70b-instruct              (solid general purpose)
# deepseek/deepseek-r1                     (reasoning, slower)


def init_backend():
    global _client
    api_key = os.getenv("NVIDIA_API_KEY", "")
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            import openai
            _client = openai.OpenAI(
                api_key=api_key,
                base_url=_base_url,
            )
            logger.info(f"NVIDIA AI client initialized (model: {_model})")
        except Exception as e:
            logger.warning(f"Failed to init AI client: {e}")
            _client = None
    else:
        logger.warning("No NVIDIA_API_KEY set - AI features disabled")
        _client = None


def _call_model(prompt: str, max_tokens: int = 1024) -> str:
    if not _client:
        return ""
    try:
        resp = _client.chat.completions.create(
            model=_model,
            messages=[
                {"role": "system", "content": "You are a legal research assistant specializing in Kenyan law. Always respond with valid JSON only, no markdown formatting, no code blocks, no commentary."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.15,
            max_tokens=max_tokens,
            top_p=0.7,
        )
        content = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
        return content
    except Exception as e:
        logger.error(f"model call failed: {e}")
        return ""


def generate_case_summary(full_text: str) -> Dict[str, Any]:
    prompt = f"""From the following Kenyan legal case text, produce a structured JSON with keys: facts, issues, holdings, ratio, obiter, cases_cited.
- facts: string (2-3 paragraphs summarizing the facts)
- issues: list of strings (the legal issues)
- holdings: list of strings (the court's holdings)
- ratio: string (the ratio decidendi)
- obiter: string (obiter dicta)
- cases_cited: list of strings (cases cited)

Return ONLY valid JSON.

Case text:
{full_text[:6000]}

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
        return {
            "facts": "Summary generation is temporarily unavailable.",
            "issues": [],
            "holdings": [],
            "ratio": "",
            "obiter": "",
            "cases_cited": []
        }


def generate_study_notes(full_text: str) -> Dict[str, Any]:
    prompt = f"""Based on the following case text, produce a structured JSON with keys: facts, issues, holdings, ratio, key_quotes, annotations.
- key_quotes: list of exact quotes (max 5)
- annotations: list of short annotation strings

Return ONLY valid JSON.

Case text:
{full_text[:6000]}

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
    prompt = f"""Compare these two Kenyan legal cases and return a structured JSON object with keys: similarities, differences, legal_proposition_a, legal_proposition_b, recommendation. Return ONLY valid JSON.

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
    prompt = f"""From the following case metadata, generate ONE flashcard in JSON format with keys front and back. front = short prompt (max 20 words). back = concise answer (max 60 words). Return ONLY valid JSON.

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
