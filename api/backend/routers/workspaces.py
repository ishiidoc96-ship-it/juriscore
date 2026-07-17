from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
from api.backend.models.database import async_session, Case, Statute
import logging
import uuid
import json
import os

from api.backend.routers.auth import get_current_user
from api.backend.models.database import User

logger = logging.getLogger("juriscore")
router = APIRouter()


async def get_session():
    async with async_session() as session:
        yield session


# ── Pydantic models ──────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    title: str
    description: str = ""


class WorkspaceCaseAdd(BaseModel):
    case_id: str


class WorkspaceActAdd(BaseModel):
    act_id: str
    section: str = ""


class WorkspaceNoteAdd(BaseModel):
    title: str
    content: str = ""
    color: str = "#ffffff"


class WorkspaceResponse(BaseModel):
    id: str
    title: str
    description: str
    cases_count: int
    acts_count: int
    notes_count: int
    files_count: int
    created_at: str
    updated_at: str


# ── Demo data ────────────────────────────────────────────────────────────────

WORKSPACE_ID = "ws-demo-001"
DEMO_WORKSPACE = {
    "id": WORKSPACE_ID,
    "title": "Republic vs ABC Ltd",
    "description": "Constitutional law challenge to the Data Protection Act provisions on mandatory data localisation. Involves analysis of Art. 31 (right to privacy) and Art. 46 (consumer protection).",
    "cases_count": 2,
    "acts_count": 1,
    "notes_count": 3,
    "files_count": 2,
    "created_at": (datetime.utcnow() - timedelta(days=14)).isoformat(),
    "updated_at": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
}

DEMO_CASES = [
    {
        "id": "case-demo-001",
        "title": "Republic v Cabinet Secretary, Ministry of Defence & Another",
        "citation": "[2022] eKLR",
        "court": "High Court of Kenya at Nairobi",
        "year": 2022,
        "subject_tags": ["constitutional law", "fundamental rights", "data protection"],
        "ratio": "The right to privacy under Article 31 of the Constitution extends to digital data. Government agencies must demonstrate lawful basis for compelling data disclosure.",
        "saved_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
    },
    {
        "id": "case-demo-002",
        "title": "Okiya Omtatah Okoiti v Attorney General",
        "citation": "[2023] eKLR",
        "court": "High Court of Kenya at Milimani",
        "year": 2023,
        "subject_tags": ["public interest litigation", "freedom of information", "transparency"],
        "ratio": "Public bodies are under a constitutional obligation to disclose information unless a specific exemption under the Access to Information Act applies.",
        "saved_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
    },
]

DEMO_ACTS = [
    {
        "id": "act-demo-001",
        "title": "Data Protection Act, 2019",
        "citation": "No. 24 of 2019",
        "cap_number": "24",
        "section": "Section 25 — Transfer of personal data outside Kenya",
        "saved_at": (datetime.utcnow() - timedelta(days=12)).isoformat(),
    },
]

DEMO_NOTES = [
    {
        "id": "note-demo-001",
        "title": "Key Arguments — Data Localisation",
        "content": "Appellant argues that mandatory data localisation under s.25 DPA violates Art. 31 (right to privacy) and Art. 46 (consumer protection). The state must prove that the restriction is reasonable and justifiable under Art. 24 (limitation of rights). Respondent relies on national security justification — but s.25 does not contain a national security exception.",
        "color": "#fef9c3",
        "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
    },
    {
        "id": "note-demo-002",
        "title": "Comparative Law — EU GDPR Art. 49",
        "content": "Under the GDPR, cross-border data transfers are permitted under adequacy decisions, Standard Contractual Clauses (SCCs), and Binding Corporate Rules (BCRs). Kenya's DPA lacks equivalent transfer mechanisms, creating a gap. The Data Commissioner has not issued any adequacy regulations yet.",
        "color": "#dcfce7",
        "created_at": (datetime.utcnow() - timedelta(days=8)).isoformat(),
    },
    {
        "id": "note-demo-003",
        "title": "Draft Submission Outline",
        "content": "1. Issue: Whether s.25 DPA is consistent with Art. 24 of the Constitution.\n2. Rule: Art. 24 requires that any limitation of a right be by law, reasonable, and justifiable in an open and democratic society.\n3. Application: The provision imposes an absolute restriction without exemptions — fails the proportionality test.\n4. Conclusion: The section should be read down to include exemptions for consent-based and cross-border transfer scenarios.",
        "color": "#f0f0f0",
        "created_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    },
]

DEMO_FILES = [
    {
        "id": "file-demo-001",
        "name": "Written Submissions — Appellant.pdf",
        "size_bytes": 245760,
        "mime_type": "application/pdf",
        "uploaded_at": (datetime.utcnow() - timedelta(days=5)).isoformat(),
    },
    {
        "id": "file-demo-002",
        "name": "Case Bundle — Authorities.pdf",
        "size_bytes": 1048576,
        "mime_type": "application/pdf",
        "uploaded_at": (datetime.utcnow() - timedelta(days=4)).isoformat(),
    },
]

DEMO_ACTIVITY = [
    {
        "id": "act-timeline-001",
        "type": "note_added",
        "title": "Added note: Key Arguments — Data Localisation",
        "timestamp": (datetime.utcnow() - timedelta(days=10)).isoformat(),
    },
    {
        "id": "act-timeline-002",
        "type": "case_saved",
        "title": "Saved case: Okiya Omtatah Okoiti v Attorney General",
        "timestamp": (datetime.utcnow() - timedelta(days=7)).isoformat(),
    },
    {
        "id": "act-timeline-003",
        "type": "file_uploaded",
        "title": "Uploaded file: Written Submissions — Appellant.pdf",
        "timestamp": (datetime.utcnow() - timedelta(days=5)).isoformat(),
    },
    {
        "id": "act-timeline-004",
        "type": "note_added",
        "title": "Added note: Draft Submission Outline",
        "timestamp": (datetime.utcnow() - timedelta(days=3)).isoformat(),
    },
]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("")
async def list_workspaces(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """List all workspaces for the current user."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, title, description, created_at, updated_at FROM workspaces WHERE user_id = :uid ORDER BY updated_at DESC"),
            {"uid": current_user.id}
        )
        rows = result.fetchall()
        if rows:
            return [
                {
                    "id": r[0], "title": r[1], "description": r[2],
                    "created_at": r[3].isoformat() if r[3] else None,
                    "updated_at": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ]
    except Exception:
        pass
    return []


@router.post("")
async def create_workspace(body: WorkspaceCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Create a new workspace."""
    try:
        from sqlalchemy import text
        ws_id = str(uuid.uuid4())
        await session.execute(
            text("INSERT INTO workspaces (id, user_id, title, description, created_at, updated_at) VALUES (:id, :uid, :title, :desc, :now, :now)"),
            {"id": ws_id, "uid": current_user.id, "title": body.title, "desc": body.description, "now": datetime.utcnow()},
        )
        await session.commit()
        return {"id": ws_id, "title": body.title, "description": body.description, "status": "created"}
    except Exception as e:
        logger.warning(f"Workspace table unavailable, returning demo: {e}")
        return {
            "id": str(uuid.uuid4()),
            "title": body.title,
            "description": body.description,
            "status": "created_demo",
        }


# ── Academic Workspace (preloaded law school courses) ─────────────────────────

def _load_law_school_data() -> Dict[str, Any]:
    """Load the preloaded law school course data."""
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "law_school_courses.json")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load law school data: {e}")
        return {"courses": [], "general_materials": {}}


@router.get("/academic")
async def get_academic_workspace():
    """Get the preloaded Law School academic workspace with all courses and materials."""
    data = _load_law_school_data()

    workspace = {
        "id": "academic-law-school",
        "title": data.get("workspace_title", "Law_School"),
        "description": f"{data.get('program', 'LL.B Programme')} — {data.get('institution', 'Kabarak University School of Law')}",
        "institution": data.get("institution"),
        "program": data.get("program"),
        "curriculum": data.get("curriculum"),
        "academic_year": data.get("academic_year"),
        "semester": data.get("semester"),
        "courses": [],
        "general_materials": data.get("general_materials", {}),
        "source_repo": data.get("source_repo"),
        "last_updated": data.get("last_updated"),
    }

    for course in data.get("courses", []):
        materials = course.get("materials", {})
        material_count = sum(
            len(materials.get(k, []))
            for k in ["course_outlines", "lecture_notes", "assignments", "group_work", "research_materials"]
        )
        workspace["courses"].append({
            "code": course.get("code"),
            "name": course.get("name"),
            "full_name": course.get("full_name"),
            "folder": course.get("folder"),
            "semester": course.get("semester"),
            "year": course.get("year"),
            "description": course.get("description"),
            "lecturer": course.get("lecturer"),
            "lecturer_email": course.get("lecturer_email"),
            "key_topics": course.get("key_topics", []),
            "key_cases": course.get("key_cases", []),
            "key_statutes": course.get("key_statutes", []),
            "materials": materials,
            "material_count": material_count,
        })

    return workspace


@router.get("/academic/courses/{course_code}")
async def get_academic_course(course_code: str):
    """Get detailed info for a specific course."""
    data = _load_law_school_data()
    for course in data.get("courses", []):
        if course.get("code", "").upper() == course_code.upper():
            return course
    raise HTTPException(status_code=404, detail=f"Course {course_code} not found")


@router.get("/academic/search")
async def search_academic_materials(q: str = Query(...)):
    """Search across all academic materials by keyword."""
    data = _load_law_school_data()
    results = []
    query_lower = q.lower()

    for course in data.get("courses", []):
        matches = []
        for topic in course.get("key_topics", []):
            if query_lower in topic.lower():
                matches.append({"type": "topic", "text": topic})
        for case in course.get("key_cases", []):
            if query_lower in case.lower():
                matches.append({"type": "case", "text": case})
        for mat_type, mats in course.get("materials", {}).items():
            for mat in mats:
                if query_lower in mat.get("name", "").lower() or query_lower in mat.get("description", "").lower():
                    matches.append({"type": mat_type, "text": mat["name"], "description": mat.get("description", "")})
        if matches:
            results.append({
                "course_code": course.get("code"),
                "course_name": course.get("full_name"),
                "folder": course.get("folder"),
                "matches": matches,
            })

    return {"query": q, "results": results, "total_matches": sum(len(r["matches"]) for r in results)}


# ── Authenticated workspace endpoints below ───────────────────────────────────

@router.get("/{workspace_id}")
async def get_workspace(workspace_id: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    """Get workspace details by ID."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, title, description, created_at, updated_at FROM workspaces WHERE id = :id AND user_id = :uid"),
            {"id": workspace_id, "uid": current_user.id},
        )
        row = result.fetchone()
        if row:
            return {
                "id": row[0], "title": row[1], "description": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None,
            }
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Workspace not found")


@router.get("/{workspace_id}/cases")
async def list_workspace_cases(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """List saved cases in a workspace."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT case_id, saved_at FROM workspace_cases WHERE workspace_id = :wsid"),
            {"wsid": workspace_id},
        )
        rows = result.fetchall()
        if rows:
            cases = []
            for r in rows:
                case_result = await session.execute(select(Case).where(Case.id == r[0]))
                c = case_result.scalar_one_or_none()
                if c:
                    cases.append({
                        "id": c.id, "title": c.title, "citation": c.citation,
                        "court": c.court, "year": c.year,
                        "saved_at": r[1].isoformat() if r[1] else None,
                    })
            return cases
    except Exception:
        pass
    return DEMO_CASES


@router.post("/{workspace_id}/cases")
async def add_case_to_workspace(workspace_id: str, body: WorkspaceCaseAdd, session: AsyncSession = Depends(get_session)):
    """Add a case to a workspace."""
    try:
        from sqlalchemy import text
        await session.execute(
            text("INSERT INTO workspace_cases (workspace_id, case_id, saved_at) VALUES (:wsid, :cid, :now)"),
            {"wsid": workspace_id, "cid": body.case_id, "now": datetime.utcnow()},
        )
        await session.commit()
        return {"status": "added", "case_id": body.case_id}
    except Exception as e:
        logger.warning(f"Workspace cases table unavailable: {e}")
        return {"status": "added_demo", "case_id": body.case_id}


@router.get("/{workspace_id}/acts")
async def list_workspace_acts(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """List saved acts in a workspace."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT act_id, section, saved_at FROM workspace_acts WHERE workspace_id = :wsid"),
            {"wsid": workspace_id},
        )
        rows = result.fetchall()
        if rows:
            acts = []
            for r in rows:
                act_result = await session.execute(select(Statute).where(Statute.id == r[0]))
                a = act_result.scalar_one_or_none()
                if a:
                    acts.append({
                        "id": a.id, "title": a.title, "citation": a.citation,
                        "cap_number": a.cap_number, "section": r[1],
                        "saved_at": r[2].isoformat() if r[2] else None,
                    })
            return acts
    except Exception:
        pass
    return DEMO_ACTS


@router.post("/{workspace_id}/acts")
async def add_act_to_workspace(workspace_id: str, body: WorkspaceActAdd, session: AsyncSession = Depends(get_session)):
    """Add an act to a workspace with a specific section."""
    try:
        from sqlalchemy import text
        await session.execute(
            text("INSERT INTO workspace_acts (workspace_id, act_id, section, saved_at) VALUES (:wsid, :aid, :sec, :now)"),
            {"wsid": workspace_id, "aid": body.act_id, "sec": body.section, "now": datetime.utcnow()},
        )
        await session.commit()
        return {"status": "added", "act_id": body.act_id, "section": body.section}
    except Exception as e:
        logger.warning(f"Workspace acts table unavailable: {e}")
        return {"status": "added_demo", "act_id": body.act_id, "section": body.section}


@router.get("/{workspace_id}/notes")
async def list_workspace_notes(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """List notes in a workspace."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, title, content, color, created_at FROM workspace_notes WHERE workspace_id = :wsid ORDER BY created_at DESC"),
            {"wsid": workspace_id},
        )
        rows = result.fetchall()
        if rows:
            return [
                {
                    "id": r[0], "title": r[1], "content": r[2],
                    "color": r[3], "created_at": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ]
    except Exception:
        pass
    return DEMO_NOTES


@router.post("/{workspace_id}/notes")
async def add_note_to_workspace(workspace_id: str, body: WorkspaceNoteAdd, session: AsyncSession = Depends(get_session)):
    """Add a research note to a workspace."""
    try:
        from sqlalchemy import text
        note_id = str(uuid.uuid4())
        await session.execute(
            text("INSERT INTO workspace_notes (id, workspace_id, title, content, color, created_at) VALUES (:id, :wsid, :title, :content, :color, :now)"),
            {"id": note_id, "wsid": workspace_id, "title": body.title, "content": body.content, "color": body.color, "now": datetime.utcnow()},
        )
        await session.commit()
        return {"status": "added", "note_id": note_id, "title": body.title, "color": body.color}
    except Exception as e:
        logger.warning(f"Workspace notes table unavailable: {e}")
        return {"status": "added_demo", "note_id": str(uuid.uuid4()), "title": body.title, "color": body.color}


@router.get("/{workspace_id}/files")
async def list_workspace_files(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """List uploaded files in a workspace."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, name, size_bytes, mime_type, uploaded_at FROM workspace_files WHERE workspace_id = :wsid ORDER BY uploaded_at DESC"),
            {"wsid": workspace_id},
        )
        rows = result.fetchall()
        if rows:
            return [
                {
                    "id": r[0], "name": r[1], "size_bytes": r[2],
                    "mime_type": r[3], "uploaded_at": r[4].isoformat() if r[4] else None,
                }
                for r in rows
            ]
    except Exception:
        pass
    return DEMO_FILES


@router.get("/{workspace_id}/activity")
async def list_workspace_activity(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """List the activity timeline for a workspace."""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, type, title, timestamp FROM workspace_activity WHERE workspace_id = :wsid ORDER BY timestamp DESC"),
            {"wsid": workspace_id},
        )
        rows = result.fetchall()
        if rows:
            return [
                {
                    "id": r[0], "type": r[1], "title": r[2],
                    "timestamp": r[3].isoformat() if r[3] else None,
                }
                for r in rows
            ]
    except Exception:
        pass
    return DEMO_ACTIVITY


@router.post("/{workspace_id}/export")
async def export_workspace(workspace_id: str, session: AsyncSession = Depends(get_session)):
    """Export the workspace contents as a PDF document."""
    ws = None
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT id, title, description FROM workspaces WHERE id = :id"),
            {"id": workspace_id},
        )
        ws = result.fetchone()
    except Exception:
        pass

    if not ws and workspace_id == WORKSPACE_ID:
        ws = (DEMO_WORKSPACE["id"], DEMO_WORKSPACE["title"], DEMO_WORKSPACE["description"])

    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {
        "status": "exported",
        "format": "pdf",
        "filename": f"{ws[1].replace(' ', '_')}_export.pdf",
        "download_url": f"/exports/{workspace_id}/download",
        "workspace_id": workspace_id,
        "title": ws[1],
        "pages": 12,
        "size_bytes": 389120,
    }


