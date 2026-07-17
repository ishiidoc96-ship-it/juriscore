from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from api.backend.core import get_session
from api.backend.models.database import (
    Workspace, WorkspaceCase, WorkspaceNote, WorkspaceFile, WorkspaceActivity
)
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter()


class WorkspaceCreate(BaseModel):
    title: str
    description: Optional[str] = ""


class NoteCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    color: Optional[str] = "#ffffff"


@router.get("/")
async def list_workspaces(user_id: str = "default", db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    result = await db.execute(select(Workspace).where(Workspace.user_id == user_id))
    workspaces = result.scalars().all()
    return [
        {"id": w.id, "title": w.title, "description": w.description, "created_at": str(w.created_at)}
        for w in workspaces
    ]


@router.post("/")
async def create_workspace(body: WorkspaceCreate, user_id: str = "default", db: AsyncSession = Depends(get_session)):
    ws = Workspace(user_id=user_id, title=body.title, description=body.description)
    db.add(ws)
    await db.commit()
    await db.refresh(ws)
    return {"id": ws.id, "title": ws.title, "description": ws.description}


@router.get("/{workspace_id}/notes")
async def list_notes(workspace_id: str, db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    result = await db.execute(select(WorkspaceNote).where(WorkspaceNote.workspace_id == workspace_id))
    notes = result.scalars().all()
    return [{"id": n.id, "title": n.title, "content": n.content, "color": n.color} for n in notes]


@router.post("/{workspace_id}/notes")
async def create_note(workspace_id: str, body: NoteCreate, db: AsyncSession = Depends(get_session)):
    note = WorkspaceNote(workspace_id=workspace_id, title=body.title, content=body.content, color=body.color)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return {"id": note.id, "title": note.title, "content": note.content}


@router.get("/{workspace_id}/activity")
async def list_activity(workspace_id: str, db: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    result = await db.execute(
        select(WorkspaceActivity).where(WorkspaceActivity.workspace_id == workspace_id).order_by(WorkspaceActivity.timestamp.desc()).limit(50)
    )
    activities = result.scalars().all()
    return [{"id": a.id, "type": a.type, "title": a.title, "timestamp": str(a.timestamp)} for a in activities]
