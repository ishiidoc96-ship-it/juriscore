import os
import json
import logging
import re
import httpx
from typing import Any, Dict, List, Optional

logger = logging.getLogger("juriscore")

_api_key = ""
_base_url = "https://integrate.api.nvidia.com/v1"
_model = "stepfun-ai/step-3.7-flash"
_fallback_model = "nvidia/llama-3.3-nemotron-super-49b-v1"  # Reliable text fallback

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
    global _api_key
    _api_key = os.getenv("NVIDIA_API_KEY", "")
    if not _api_key:
        _api_key = os.getenv("OPENAI_API_KEY", "")
    if _api_key:
        logger.info(f"NVIDIA AI service initialized (model: {_model})")
    else:
        logger.warning("No NVIDIA_API_KEY set - AI features disabled")


async def _call_model(prompt: str, max_tokens: int = 1024, system: str = None, temperature: float = 0.7) -> str:
    """Call NVIDIA API asynchronously using httpx directly."""
    if not _api_key:
        logger.warning("_call_model called but no API key set")
        return ""
    models_to_try = [_model, _fallback_model]
    for model in models_to_try:
        try:
            messages = [
                {"role": "system", "content": system or HUMANIZE_SYSTEM},
                {"role": "user", "content": prompt}
            ]
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.9,
            }
            headers = {
                "Authorization": f"Bearer {_api_key}",
                "Content-Type": "application/json",
            }
            async with httpx.AsyncClient(timeout=90) as client:
                resp = await client.post(
                    f"{_base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"].strip()
                # Strip thinking tags if present (step-3.7-flash may include reasoning)
                content = re.sub(r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL).strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content)
                    content = re.sub(r"\s*```$", "", content)
                if content and len(content) > 5:
                    return content
                logger.warning(f"Model {model} returned empty/short response, trying next")
        except httpx.HTTPStatusError as e:
            logger.error(f"Model {model} HTTP error {e.response.status_code}: {e.response.text[:500]}")
        except Exception as e:
            logger.error(f"Model {model} failed: {type(e).__name__}: {e}")
    return ""


def _parse_json(text: str, fallback: Any = None) -> Any:
    """Safely parse JSON from model output."""
    try:
        return json.loads(text)
    except Exception:
        return fallback


# ---------- Case Summary ----------

async def generate_case_summary(full_text: str) -> Dict[str, Any]:
    prompt = f"""Analyse this Kenyan legal case using the IRAC method (Issue, Rule, Application, Conclusion). Write like a senior law tutor breaking down a case for a student preparing for exams — precise, authoritative, specific.

Return ONLY valid JSON with these keys:
- facts: string (2-3 paragraphs. Name the parties, the court, the date, the key facts. Be specific — dates, amounts, names, sections cited.)
- issues: list of strings (the legal issues framed as questions the court had to answer)
- rule: string (the applicable legal rules — constitutional provisions, statutory sections, precedent cases cited)
- application: string (how the court applied the rules to the facts — the reasoning chain. This is the most important part.)
- conclusion: string (the court's final decision and order)
- ratio: string (the ratio decidendi — the binding legal principle from this case, cite it properly as: Case Name [Year] court citation)
- obiter: string (obiter dicta — persuasive but non-binding observations)
- cases_cited: list of strings (each case properly cited)
- significance: string (why this case matters for Kenyan law — what principle did it establish or confirm?)

Case text:
{full_text[:6000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        for key in ["facts", "issues", "rule", "application", "conclusion", "ratio", "obiter", "cases_cited", "significance"]:
            parsed.setdefault(key, "" if key in ["facts", "rule", "application", "conclusion", "ratio", "obiter", "significance"] else [])
        return parsed
    return {
        "facts": "Summary generation is temporarily unavailable. Please try again.",
        "issues": [], "rule": "", "application": "", "conclusion": "", "ratio": "", "obiter": "", "cases_cited": [], "significance": ""
    }


# ---------- Study Notes ----------

async def generate_study_notes(full_text: str) -> Dict[str, Any]:
    prompt = f"""Create exam-ready study notes for this case using the IRAC method. Write like a top student's personal case brief — the kind you'd share before an exam.

Return ONLY valid JSON with:
- facts: string (concise factual background — who, what, when, where)
- issues: list (legal issues framed as exam questions)
- rule: string (the applicable legal rules — statutes, constitutional provisions, precedent)
- application: string (how the court applied the rules to the facts)
- conclusion: string (the court's final decision)
- ratio: string (the ratio decidendi — the rule you'd write in an exam answer)
- key_quotes: list of exact quotes from the judgment (max 5, max 40 words each)
- significance: string (why this case matters for Kenyan law)

Case text:
{full_text[:6000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        for key in ["facts", "issues", "rule", "application", "conclusion", "ratio", "key_quotes", "significance"]:
            parsed.setdefault(key, "" if key in ["facts", "rule", "application", "conclusion", "ratio", "significance"] else [])
        return parsed
    return {"facts": "", "issues": [], "rule": "", "application": "", "conclusion": "", "ratio": "", "key_quotes": [], "significance": ""}


# ---------- Citation ----------

async def generate_citation(case_data: Dict) -> Dict[str, str]:
    prompt = f"""Format this case data into a proper Kenyan eKLR citation. Be precise.

Return ONLY valid JSON with: parties, year, court, neutral_citation, formatted.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.3)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        for key in ["parties", "year", "court", "neutral_citation", "formatted"]:
            parsed.setdefault(key, "")
        return parsed
    return {"parties": "", "year": "", "court": "", "neutral_citation": "", "formatted": ""}


# ---------- Case Comparison ----------

async def compare_cases(case_a_text: str, case_b_text: str) -> Dict[str, Any]:
    prompt = f"""Compare these two Kenyan cases. Don't just list similarities — actually analyse whether they're consistent, distinguishable, or in tension.

Return ONLY valid JSON with: similarities, differences, legal_proposition_a, legal_proposition_b, recommendation.

Case A:
{case_a_text[:4000]}

Case B:
{case_b_text[:4000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        for key in ["similarities", "differences", "legal_proposition_a", "legal_proposition_b", "recommendation"]:
            parsed.setdefault(key, [])
        return parsed
    return {"similarities": [], "differences": [], "legal_proposition_a": "", "legal_proposition_b": "", "recommendation": ""}


# ---------- Flashcard ----------

async def generate_flashcard(case_data: Dict) -> Dict[str, str]:
    prompt = f"""From this case, create ONE flashcard that would actually help during exam revision.

front = a specific question about the holding, ratio, or a key fact (max 20 words)
back = concise answer with the case name and principle (max 60 words)

Return ONLY valid JSON with keys front and back.

{json.dumps(case_data)[:2000]}

JSON:"""
    raw = await _call_model(prompt, temperature=0.5)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        parsed.setdefault("front", "What is the holding?")
        parsed.setdefault("back", "TBD")
        return parsed
    return {"front": "What is the holding?", "back": "TBD"}


# ---------- Summary from Metadata ----------

async def generate_summary_from_metadata(title: str, citation: str, court: str, date: str, doc_type: str, excerpt: str = "") -> str:
    """Generate a natural-language summary from search result metadata."""
    prompt = f"""Analyse this Kenyan legal document using the IRAC method. Write like a law tutor who has read hundreds of these — authoritative, specific, no fluff.

Structure your analysis as:
1. ISSUE: What legal question does this document address?
2. RULE: What are the applicable legal principles, constitutional provisions, or statutory provisions?
3. APPLICATION: How does this document apply or relate to those principles?
4. CONCLUSION: What is the significance? What should a law student remember about this?

CRITICAL FORMATTING RULES:
- Do NOT use markdown. No **bold**, no *italic*, no bullet points with dashes or asterisks.
- Write in plain text only. Use short paragraphs separated by blank lines.
- If you need emphasis, just state it directly. No special characters.

Document details:
- Title: {title}
- Citation: {citation}
- Court: {court}
- Date: {date}
- Type: {doc_type}
- Excerpt: {excerpt}

Write 3-4 paragraphs. Be specific — name cases, cite sections, reference articles. Don't use AI words like "delve", "comprehensive", or "in conclusion"."""""

    result = await _call_model(prompt, max_tokens=800, temperature=0.6)
    return result if result else f"Summary unavailable for: {title}"


# ---------- Key Quotes ----------

async def extract_key_quotes(text: str, max_quotes: int = 5) -> List[str]:
    prompt = f"""Extract up to {max_quotes} key legal quotes from this text. Pick the ones a student would highlight for an exam.

Return ONLY a JSON array of strings (max 40 words each).

{text[:6000]}

JSON:"""
    raw = await _call_model(prompt, max_tokens=512, temperature=0.4)
    parsed = _parse_json(raw, [])
    if isinstance(parsed, list):
        return parsed[:max_quotes]
    return []


# ---------- AI Search ----------

QUERY_REWRITE_SYSTEM = """You are an expert legal search assistant specializing in Kenyan law and the KenyaLaw.org database.

Your task: take a user's search query and produce an improved search query that will find the best results from KenyaLaw.org.

THINK STEP BY STEP:
1. Identify what the user is actually looking for (case name, legal topic, statute, court, etc.)
2. Fix ALL misspellings and typos (e.g. "constituion" → "constitution", "crimnal" → "criminal", "Odhiambo" → "Ochieng" if that's the common spelling)
3. Expand abbreviations: MR → Mining Regulations, EMCA → Environmental Management Act, CPC → Criminal Procedure Code, KLR → Kenya Law Reports
4. If the query is a case name, keep it but fix spelling and add the year if known
5. If the query is vague, add legal context (e.g. "land dispute" → "land dispute property ownership Kenya")
6. If the query mentions a specific area of law, add relevant statute names
7. Consider both Swahili and English legal terms

Return ONLY a JSON object: {"query": "corrected search query", "suggestions": ["alternative search 1", "alternative search 2", "alternative search 3"], "reasoning": "brief explanation of what you changed and why"}

RULES:
- Keep the main query under 15 words
- suggestions should be 1-3 related searches the user might also want
- reasoning should be one sentence explaining your changes"""


async def rewrite_search_query(query: str) -> Dict[str, Any]:
    """Use AI to correct misspellings and expand search queries with chain-of-thought reasoning."""
    if not _api_key or len(query.strip()) < 2:
        return {"query": query, "suggestions": [], "corrected": False}

    prompt = f"""Correct and improve this legal search query for KenyaLaw.org.

User's query: "{query}"

Think through:
1. What is the user looking for? (case/legislation/topic)
2. Are there any misspellings?
3. What abbreviations need expanding?
4. What additional terms would improve results?

Then return JSON: {{"query": "corrected query", "suggestions": ["alt1", "alt2"], "reasoning": "what you changed"}}"""

    raw = await _call_model(prompt, max_tokens=300, system=QUERY_REWRITE_SYSTEM, temperature=0.3)
    parsed = _parse_json(raw, {})
    if isinstance(parsed, dict):
        corrected_query = parsed.get("query", query).strip()
        suggestions = parsed.get("suggestions", [])
        reasoning = parsed.get("reasoning", "")
        corrected = corrected_query.lower().replace(" ", "") != query.lower().replace(" ", "")
        if reasoning:
            logger.info(f"AI query rewrite reasoning: {reasoning}")
        return {"query": corrected_query, "suggestions": suggestions[:3], "corrected": corrected}
    return {"query": query, "suggestions": [], "corrected": False}


RANK_SYSTEM = """You are a legal research expert specializing in Kenyan law. Your task is to rank search results by their relevance to a user's query.

THINK STEP BY STEP for each result:
1. Does the title match what the user is looking for?
2. Is the court/jurisdiction relevant?
3. Is the document type what they want (case, legislation, etc.)?
4. Is the date/recentness relevant?
5. Overall relevance score (0-10)

Then rank from most relevant to least relevant."""


async def rank_search_results(query: str, results: List[Dict], top_n: int = 30) -> List[Dict]:
    """Use AI to re-rank search results by relevance with chain-of-thought reasoning."""
    if not _api_key or not results:
        return results

    listing = "\n".join(
        f"[{i}] {r.get('title', 'Untitled')} | Court: {r.get('court', 'N/A')} | Type: {r.get('doc_type', 'N/A')} | Date: {r.get('date', 'N/A')} | Excerpt: {r.get('excerpt', '')[:100]}"
        for i, r in enumerate(results)
    )

    prompt = f"""Rank these search results by relevance to the query: "{query}"

Results:
{listing}

For each result, briefly note why it is or isn't relevant, then return ONLY a JSON array of indices in order of relevance (most relevant first).
Return at most {top_n} indices. Only include results that are actually relevant (score >= 5).

Example: [0, 5, 2, 8]"""

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

    raw = await _call_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
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

    result = await _call_model(prompt, max_tokens=800, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
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

    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
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

    result = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
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

    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
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

    raw = await _call_model(prompt, max_tokens=1500, system=LEGAL_RESEARCH_SYSTEM, temperature=0.4)
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

    raw = await _call_model(prompt, max_tokens=2000, system=LEGAL_RESEARCH_SYSTEM, temperature=0.5)
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
