"""
Chat router — clean legal research interface.

Zero AI references in responses. Anti-AI writer optimization by default.
Session memory for learning and adaptation. Backend uses powerful AI reasoning
but the frontend only sees clean, professional legal research results.
"""
import json
import logging
import re
import uuid
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger("juriscore")
router = APIRouter()

# ── In-memory session store (per-server; swap for Redis/DB in production) ─────
_sessions: Dict[str, Dict[str, Any]] = {}

# ── Anti-AI Writer: Banned Words & Phrases (2026 detectors) ──────────────────
# These are instant AI flags to any detector (GPTZero, Turnitin, Originality.ai)
_BANNED_PHRASES = [
    # Direct AI self-reference
    "as an ai", "as a language model", "i'm an ai", "i am an ai",
    "based on my knowledge", "from my training data",
    "as of my last update", "as of my knowledge cutoff",
    "i don't have real-time", "i cannot access the internet",
    "i'm unable to browse", "i don't have access to",
    "i hope this helps", "let me know if you have any questions",
    "feel free to ask", "don't hesitate to reach out",
    # AI structural tells (2026 detectors)
    "it is important to note", "it is worth noting", "it should be noted",
    "please note that", "it is worth mentioning",
    "in conclusion", "in summary", "to summarize",
    "furthermore", "moreover", "additionally", "consequently",
    "it is imperative that", "it is essential that",
    "this essay will", "this paper will", "this report will",
    "in order to understand", "having established",
    "building on the above", "as previously mentioned",
    "as discussed above", "as we can see",
    # Overused AI adjectives
    "comprehensive", "robust", "pivotal", "paramount",
    "crucial", "essential", "nuanced", "multifaceted",
    "holistic", "groundbreaking", "revolutionary",
    # AI transition patterns
    "a plethora of", "at the end of the day",
    "in today's fast-paced world", "in this day and age",
    "take a deep dive", "shed light on",
    "plays a crucial role", "serves as a foundation",
    "serves to highlight", "as evidenced by",
    "it can be argued that", "it could be argued that",
    "a wide range of", "in the realm of",
    "with regard to", "in terms of", "the fact that",
    "delve", "leverage", "utilize", "navigate",
    "underscore", "tapestry", "journey", "game-changer",
    "seamlessly", "unpack",
]

# Direct replacements for banned patterns
_BANNED_REPLACEMENTS = {
    "Furthermore,": "Also,",
    "Moreover,": "Beyond that,",
    "Additionally,": "On top of that,",
    "Consequently,": "As a result,",
    "In conclusion,": "To wrap up,",
    "It is important to note that": "Worth mentioning:",
    "It should be noted that": "Keep in mind:",
    "In summary,": "Bottom line:",
    "In terms of": "For",
    "With regard to": "On",
    "As evidenced by": "Shown by",
    "It can be argued that": "The stronger view is",
    "It could be argued that": "One reading is",
    "A wide range of": "Several",
    "plays a crucial role": "matters here",
    "serves as a foundation": "underpins",
    "serves to highlight": "shows",
}


def _anti_ai_writer(text: str) -> str:
    """
    Post-process text to remove AI-sounding patterns and raise
    perplexity + burstiness scores for AI detectors.

    This is the statistical humanization layer. It does:
    1. Remove banned phrases that flag AI
    2. Replace AI transitions with human alternatives
    3. Remove dashes/hyphens (flagged by 2026 detectors)
    4. Clean up orphaned punctuation
    """
    if not text:
        return text

    result = text

    # Step 1: Remove banned phrases (case-insensitive)
    for phrase in _BANNED_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        result = pattern.sub("", result)

    # Step 2: Apply direct replacements
    for ai_phrase, human_phrase in _BANNED_REPLACEMENTS.items():
        result = result.replace(ai_phrase, human_phrase)

    # Step 3: Remove dashes and hyphens (2026 AI detectors flag these)
    # Replace em-dashes, en-dashes, and double-hyphens with commas or restructure
    result = result.replace(" -- ", ", ")
    result = result.replace(" — ", ", ")
    result = result.replace(" – ", ", ")
    result = result.replace("--", ", ")

    # Step 4: Clean up double spaces and orphaned punctuation
    result = re.sub(r"  +", " ", result)
    result = re.sub(r"\s+([.,;:!?])", r"\1", result)
    result = re.sub(r"^[,;:!?\s]+", "", result)
    result = re.sub(r"\n{3,}", "\n\n", result)

    # Step 5: Fix sentences that start with "This" + verb (AI tell)
    result = re.sub(
        r"\bThis (demonstrates|shows|highlights|illustrates|confirms|underscores)\b",
        r"Here, \1",
        result,
    )

    return result.strip()


def _get_or_create_session(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Get existing session or create a new one."""
    if session_id and session_id in _sessions:
        return _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())
    session = {
        "id": new_id,
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
        "last_active": datetime.utcnow().isoformat(),
        "context": {},
    }
    _sessions[new_id] = session
    return session


def _build_conversation_context(session: Dict[str, Any], limit: int = 10) -> str:
    """Build conversation context from recent messages for the AI."""
    recent = session["messages"][-limit:]
    if not recent:
        return ""

    context_lines = []
    for msg in recent:
        role = "User" if msg.get("role") == "user" else "Assistant"
        context_lines.append(f"{role}: {msg.get('content', '')}")

    return "\n".join(context_lines)


def _detect_search_intent(message: str) -> Dict[str, Any]:
    """Detect if the user wants to search vs. ask a question."""
    msg_lower = message.lower().strip()

    search_keywords = [
        "search", "find", "look up", "lookup", "look for",
        "case about", "cases about", "find me", "show me",
        "get me", "retrieve", "fetch",
    ]
    is_search = any(kw in msg_lower for kw in search_keywords)

    question_keywords = [
        "what is", "what are", "explain", "define", "how does",
        "how do", "why", "when did", "can you", "tell me about",
        "describe", "discuss", "analyze", "compare",
    ]
    is_question = any(kw in msg_lower for kw in question_keywords)

    return {"is_search": is_search, "is_question": is_question, "message": message}


# ── Pydantic models ──────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    results: Optional[List[Dict[str, Any]]] = None
    sources: Optional[List[str]] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]


# ── System prompt with full anti-AI writing instructions ─────────────────────

_SYSTEM_PROMPT = """You are a senior legal researcher and analyst at a Kenyan law firm.
You provide thorough, well-structured legal research responses.

CRITICAL RULES — VIOLATION IS UNACCEPTABLE:
1. NEVER mention AI, artificial intelligence, language models, or being an AI
2. NEVER use phrases like "as an AI", "based on my knowledge", "I hope this helps"
3. NEVER use dashes or hyphens in your output (they are flagged by detectors)
4. NEVER use these words: delve, robust, comprehensive, pivotal, paramount, crucial,
   essential, nuanced, multifaceted, holistic, groundbreaking, revolutionary, seamlessly,
   leverage, utilize, navigate, underscore, tapestry, journey, game-changer, unpack
5. NEVER start a paragraph with "Furthermore", "Moreover", "Additionally", "In conclusion"
6. NEVER start a sentence with "This" followed by a verb (This shows, This demonstrates)

WRITING STYLE (Anti-AI, Human-Sounding):
- Vary sentence length dramatically. Mix 5-word sentences with 30-word sentences.
- Write with opinions, not hedges. Commit to positions. Say "the court was wrong" not
  "it could be argued that the court may have erred"
- Be specific. Name cases, cite statutes, reference articles. Never be vague.
- Use contractions in transitions and asides: "That's not what the ratio says."
- End paragraphs with your strongest point, not a summary.
- No bullet-point lists unless the user specifically asks for one.
- One sentence paragraphs are fine. Use them for emphasis.
- Start some sentences with "But" or "And" or "So"
- Use em dashes sparingly, not at all if possible (detectors flag them)
- If you need a break in a sentence, use a comma or start a new sentence.

LEGAL WRITING VOICE:
- "It is submitted that..." (legal convention, stays)
- Case citations in standard format: Case Name [Year] eKLR
- Statute citations: Act Name (Cap. XX, Laws of Kenya)
- IRAC structure for problem questions
- Commit to your analysis. Don't qualify every claim into meaninglessness.

TRANSITIONS TO USE (human-sounding):
- But. And. Which means. That is the problem.
- Here is why that matters. The real question is.
- Three years later, the court revisited this.
- None of this would matter except that...
- The short answer is no.

NEVER USE THESE TRANSITIONS:
- Furthermore, Moreover, In addition, Additionally,
- On the other hand, Having said that, With that in mind,
- It is important to highlight, Last but not least,
- In today's world, It goes without saying"""

# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/send", response_model=ChatResponse)
async def send_message(body: ChatMessage):
    """
    Send a message and get a clean legal research response.
    No AI references in output. Anti-AI writer optimization applied.
    """
    from api.backend.services.ai_service import _call_model
    from api.backend.services.brain import brain_search
    from api.backend.services.local_db import search_local_db
    from api.backend.services.scraper import search_kenyalaw

    session = _get_or_create_session(body.session_id)
    message = body.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Store user message
    session["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": datetime.utcnow().isoformat(),
    })
    session["last_active"] = datetime.utcnow().isoformat()

    # Detect intent
    intent = _detect_search_intent(message)

    # Build conversation context for AI
    conversation_context = _build_conversation_context(session)

    # Step 1: Search multiple sources
    search_results = []
    sources_used = []

    try:
        local_results = search_local_db(message, limit=5)
        if local_results:
            for r in local_results:
                r["source"] = "local_database"
            search_results.extend(local_results)
            sources_used.append("local_database")
    except Exception as e:
        logger.warning(f"Local DB search failed: {e}")

    try:
        brain_result = brain_search(message, limit=5)
        if brain_result.get("results"):
            for r in brain_result["results"]:
                r["source"] = "brain"
            search_results.extend(brain_result["results"])
            sources_used.append("brain")
    except Exception as e:
        logger.warning(f"Brain search failed: {e}")

    try:
        import asyncio
        kenya_results = await asyncio.wait_for(
            search_kenyalaw(query=message, limit=5),
            timeout=8,
        )
        if kenya_results.get("results"):
            for r in kenya_results["results"]:
                r["source"] = "kenyalaw"
            search_results.extend(kenya_results["results"])
            sources_used.append("kenyalaw")
    except Exception as e:
        logger.warning(f"KenyaLaw search failed: {e}")

    # Deduplicate by title
    seen_titles = set()
    unique_results = []
    for r in search_results:
        t = r.get("title", "")
        if t and t not in seen_titles:
            seen_titles.add(t)
            unique_results.append(r)
    search_results = unique_results[:8]

    # Step 2: Build AI prompt
    results_json = json.dumps(search_results[:5], indent=2, default=str) if search_results else "No specific results found in databases."

    context_block = f"\n\nPrevious conversation:\n{conversation_context}" if conversation_context else ""
    results_block = f"\n\nRELEVANT AUTHORITIES:\n{results_json}" if search_results else ""

    user_prompt = f"""Research query: "{message}"
{results_block}
{context_block}

Provide a thorough, well-structured response. Include specific citations where available."""

    # Step 3: Get AI response
    ai_response = ""
    try:
        ai_response = await _call_model(
            f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
            max_tokens=2048,
            temperature=0.3,
        )
    except Exception as e:
        logger.warning(f"AI response generation failed: {e}")

    # Step 3b: Fallback if AI returned empty or failed
    if not ai_response or not ai_response.strip():
        if search_results:
            ai_response = _format_results_fallback(message, search_results)
        else:
            ai_response = f"No results found for \"{message}\". Try rephrasing your query or use the search page for a broader lookup."

    # Step 4: Apply anti-AI writer optimization
    clean_response = _anti_ai_writer(ai_response)

    # Step 5: Store assistant response
    session["messages"].append({
        "role": "assistant",
        "content": clean_response,
        "timestamp": datetime.utcnow().isoformat(),
        "sources": sources_used,
    })

    # Step 6: Return clean response (zero AI references)
    return ChatResponse(
        response=clean_response,
        session_id=session["id"],
        results=search_results if search_results else None,
        sources=sources_used if sources_used else None,
    )


def _format_results_fallback(query: str, results: List[Dict]) -> str:
    """Format search results into a clean response without AI."""
    lines = [f"Here are the results for your query about \"{query}\":\n"]

    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "Untitled")
        citation = r.get("citation", "")
        court = r.get("court", "")
        year = r.get("year", "")
        excerpt = r.get("excerpt", "")

        line = f"**{i}. {title}**"
        if citation:
            line += f" -- {citation}"
        if court:
            line += f" ({court}"
            if year:
                line += f", {year}"
            line += ")"
        lines.append(line)

        if excerpt:
            lines.append(f"   {excerpt[:200]}...")
        lines.append("")

    return "\n".join(lines)


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
    session = _get_or_create_session(session_id)
    return ChatHistoryResponse(
        session_id=session["id"],
        messages=session["messages"],
    )


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a chat session."""
    if session_id in _sessions:
        del _sessions[session_id]
    return {"status": "cleared", "session_id": session_id}


@router.get("/sessions")
async def list_sessions():
    """List all active sessions (for admin/debug)."""
    return {
        "count": len(_sessions),
        "sessions": [
            {
                "id": s["id"],
                "message_count": len(s["messages"]),
                "created_at": s["created_at"],
                "last_active": s["last_active"],
            }
            for s in _sessions.values()
        ],
    }
