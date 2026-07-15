"""Notebook endpoints — CRUD for notebook folders and entries."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Notebook, NotebookEntry
from models.schemas import (
    NotebookEntryCreate,
    NotebookEntryResponse,
    NotebookFolderCreate,
    NotebookFolderResponse,
    NotebookFolderUpdate,
)
from core import get_session

logger = logging.getLogger("juriscore.router.notebook")
router = APIRouter()


@router.get("/folders", response_model=List[NotebookFolderResponse])
async def list_folders(user_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Notebook).where(Notebook.user_id == user_id)
    )
    return [NotebookFolderResponse.model_validate(n) for n in result.scalars().all()]


@router.post("/folders", response_model=NotebookFolderResponse, status_code=201)
async def create_folder(
    payload: NotebookFolderCreate,
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    notebook = Notebook(user_id=user_id, name=payload.name)
    session.add(notebook)
    await session.flush()
    await session.commit()
    return NotebookFolderResponse.model_validate(notebook)


@router.put("/folders/{folder_id}", response_model=NotebookFolderResponse)
async def update_folder(
    folder_id: str,
    payload: NotebookFolderUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Notebook).where(Notebook.id == folder_id))
    notebook = result.scalar_one_or_none()
    if not notebook:
        from fastapi import HTTPException
        from fastapi import status as http_status
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Folder not found")
    notebook.name = payload.name
    await session.commit()
    return NotebookFolderResponse.model_validate(notebook)


@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(folder_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Notebook).where(Notebook.id == folder_id))
    notebook = result.scalar_one_or_none()
    if notebook:
        await session.delete(notebook)
        await session.commit()
    return None


@router.post("/folders/{folder_id}/entries", response_model=NotebookEntryResponse)
async def add_entry(
    folder_id: str,
    payload: NotebookEntryCreate,
    session: AsyncSession = Depends(get_session),
):
    entry = NotebookEntry(
        notebook_id=folder_id,
        case_id=payload.case_id,
        statute_id=payload.statute_id,
        note_text=payload.note_text,
    )
    session.add(entry)
    await session.flush()
    await session.commit()
    return NotebookEntryResponse.model_validate(entry)


@router.delete("/entries/{entry_id}", status_code=204)
async def delete_entry(entry_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(NotebookEntry).where(NotebookEntry.id == entry_id)
    )
    entry = result.scalar_one_or_none()
    if entry:
        await session.delete(entry)
        await session.commit()
    return None


@router.get("/recent")
async def get_recent(
    user_id: str,
    limit: int = 5,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(NotebookEntry)
        .join(Notebook)
        .where(Notebook.user_id == user_id)
        .order_by(desc(NotebookEntry.created_at))
        .limit(limit)
    )
    return [
        {
            "id": e.id,
            "notebook_id": e.notebook_id,
            "case_id": e.case_id,
            "statute_id": e.statute_id,
            "note_text": e.note_text,
            "created_at": e.created_at,
        }
        for e in result.scalars().all()
    ]
