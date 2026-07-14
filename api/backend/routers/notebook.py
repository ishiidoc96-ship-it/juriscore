from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from models.database import async_session, Notebook, NotebookEntry
from models.schemas import NotebookFolderCreate, NotebookFolderUpdate, NotebookEntryCreate, NotebookEntryResponse, NotebookFolderResponse
import logging

router = APIRouter()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


@router.get("/folders", response_model=List[NotebookFolderResponse])
async def list_folders(user_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Notebook).where(Notebook.user_id == user_id))
    notebooks = result.scalars().all()
    return [NotebookFolderResponse(id=n.id, user_id=n.user_id, name=n.name, created_at=n.created_at) for n in notebooks]


@router.post("/folders", response_model=NotebookFolderResponse)
async def create_folder(payload: NotebookFolderCreate, user_id: str, session: AsyncSession = Depends(get_session)):
    notebook = Notebook(user_id=user_id, name=payload.name)
    session.add(notebook)
    await session.flush()
    await session.commit()
    return NotebookFolderResponse(id=notebook.id, user_id=notebook.user_id, name=notebook.name, created_at=notebook.created_at)


@router.put("/folders/{folder_id}", response_model=NotebookFolderResponse)
async def update_folder(folder_id: str, payload: NotebookFolderUpdate, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Notebook).where(Notebook.id == folder_id))
    notebook = result.scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Folder not found")
    notebook.name = payload.name
    await session.commit()
    return NotebookFolderResponse(id=notebook.id, user_id=notebook.user_id, name=notebook.name, created_at=notebook.created_at)


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Notebook).where(Notebook.id == folder_id))
    notebook = result.scalar_one_or_none()
    if not notebook:
        raise HTTPException(status_code=404, detail="Folder not found")
    await session.delete(notebook)
    await session.commit()
    return {"status": "deleted"}


@router.post("/folders/{folder_id}/entries", response_model=NotebookEntryResponse)
async def add_entry(folder_id: str, payload: NotebookEntryCreate, session: AsyncSession = Depends(get_session)):
    entry = NotebookEntry(
        notebook_id=folder_id,
        case_id=payload.case_id,
        statute_id=payload.statute_id,
        note_text=payload.note_text,
    )
    session.add(entry)
    await session.flush()
    await session.commit()
    return NotebookEntryResponse(
        id=entry.id,
        notebook_id=entry.notebook_id,
        case_id=entry.case_id,
        statute_id=entry.statute_id,
        note_text=entry.note_text,
        created_at=entry.created_at,
    )


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(NotebookEntry).where(NotebookEntry.id == entry_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await session.delete(entry)
    await session.commit()
    return {"status": "deleted"}


@router.get("/recent")
async def get_recent(user_id: str, limit: int = 5, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(NotebookEntry).join(Notebook).where(Notebook.user_id == user_id).order_by(desc(NotebookEntry.created_at)).limit(limit)
    )
    entries = result.scalars().all()
    return [
        {
            "id": e.id,
            "notebook_id": e.notebook_id,
            "case_id": e.case_id,
            "statute_id": e.statute_id,
            "note_text": e.note_text,
            "created_at": e.created_at,
        }
        for e in entries
    ]
