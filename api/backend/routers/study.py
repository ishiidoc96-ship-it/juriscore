from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from api.backend.models.database import async_session, StudyNote
from api.backend.models.schemas import StudyNoteCreate, StudyNoteUpdate, StudyNoteResponse, GenerateNotesRequest
from api.backend.services.ai_service import generate_study_notes
from datetime import datetime
import json
import logging

from api.backend.routers.auth import get_current_user
from api.backend.models.database import User

router = APIRouter()


async def get_session():
    async with async_session() as session:
        yield session


@router.get("/notes", response_model=List[StudyNoteResponse])
async def list_notes(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(StudyNote).where(StudyNote.user_id == current_user.id))
    notes = result.scalars().all()
    return [
        StudyNoteResponse(
            id=n.id, user_id=n.user_id, case_id=n.case_id,
            statute_id=n.statute_id, note_text=n.note_text,
            created_at=n.created_at, updated_at=n.updated_at,
        )
        for n in notes
    ]


@router.post("/notes", response_model=StudyNoteResponse)
async def create_note(payload: StudyNoteCreate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    note = StudyNote(
        user_id=current_user.id,
        case_id=payload.case_id,
        statute_id=payload.statute_id,
        note_text=payload.note_text,
    )
    session.add(note)
    await session.flush()
    await session.commit()
    return StudyNoteResponse(
        id=note.id, user_id=note.user_id, case_id=note.case_id,
        statute_id=note.statute_id, note_text=note.note_text,
        created_at=note.created_at, updated_at=note.updated_at,
    )


@router.put("/notes/{note_id}", response_model=StudyNoteResponse)
async def update_note(note_id: str, payload: StudyNoteUpdate, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(StudyNote).where(StudyNote.id == note_id, StudyNote.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    note.note_text = payload.note_text
    note.updated_at = datetime.utcnow()
    await session.commit()
    return StudyNoteResponse(
        id=note.id, user_id=note.user_id, case_id=note.case_id,
        statute_id=note.statute_id, note_text=note.note_text,
        created_at=note.created_at, updated_at=note.updated_at,
    )


@router.delete("/notes/{note_id}")
async def delete_note(note_id: str, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(StudyNote).where(StudyNote.id == note_id, StudyNote.user_id == current_user.id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    await session.delete(note)
    await session.commit()
    return {"status": "deleted"}


@router.post("/notes/generate")
async def generate_notes(payload: GenerateNotesRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    from api.backend.models.database import Case
    result = await session.execute(select(Case).where(Case.id == payload.case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    notes = await generate_study_notes(case.full_text)
    note = StudyNote(
        user_id=current_user.id,
        case_id=case.id,
        note_text=json.dumps(notes),
    )
    session.add(note)
    await session.flush()
    await session.commit()
    return notes
