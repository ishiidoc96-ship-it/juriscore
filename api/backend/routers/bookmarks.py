from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
from models.database import async_session, Base, engine, uuid_str
from sqlalchemy import String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    resource_type: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    collection_id: Mapped[str | None] = mapped_column(String, ForeignKey("collections.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BookmarkCreate(BaseModel):
    resource_type: str
    resource_id: str
    title: str
    metadata: Optional[dict] = None


class BookmarkMoveRequest(BaseModel):
    collection_id: Optional[str] = None


class CollectionCreate(BaseModel):
    name: str


class BookmarkResponse(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    title: str
    metadata: Optional[dict] = None
    collection_id: Optional[str] = None
    created_at: datetime


class CollectionResponse(BaseModel):
    id: str
    name: str
    created_at: datetime


async def get_session():
    async with async_session() as session:
        yield session


@router.get("/", response_model=List[BookmarkResponse])
async def list_bookmarks(
    tab: Optional[str] = Query(None, description="Filter by resource type: cases, statutes, gazettes, notes"),
    session: AsyncSession = Depends(get_session),
):
    try:
        stmt = select(Bookmark)
        if tab:
            stmt = stmt.where(Bookmark.resource_type == tab)
        stmt = stmt.order_by(Bookmark.created_at.desc())
        result = await session.execute(stmt)
        bookmarks = result.scalars().all()
        return [
            BookmarkResponse(
                id=b.id,
                resource_type=b.resource_type,
                resource_id=b.resource_id,
                title=b.title,
                metadata=b.metadata_json,
                collection_id=b.collection_id,
                created_at=b.created_at,
            )
            for b in bookmarks
        ]
    except Exception as e:
        logger.error(f"list_bookmarks error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load bookmarks: {str(e)}")


@router.post("/", response_model=BookmarkResponse, status_code=201)
async def create_bookmark(
    payload: BookmarkCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        bookmark = Bookmark(
            id=uuid_str(),
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            title=payload.title,
            metadata_json=payload.metadata,
        )
        session.add(bookmark)
        await session.flush()
        await session.commit()
        return BookmarkResponse(
            id=bookmark.id,
            resource_type=bookmark.resource_type,
            resource_id=bookmark.resource_id,
            title=bookmark.title,
            metadata=bookmark.metadata_json,
            collection_id=bookmark.collection_id,
            created_at=bookmark.created_at,
        )
    except Exception as e:
        logger.error(f"create_bookmark error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create bookmark: {str(e)}")


@router.delete("/{bookmark_id}", status_code=204)
async def delete_bookmark(
    bookmark_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        await session.delete(bookmark)
        await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_bookmark error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete bookmark: {str(e)}")


@router.post("/{bookmark_id}/move", response_model=BookmarkResponse)
async def move_bookmark(
    bookmark_id: str,
    payload: BookmarkMoveRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.execute(select(Bookmark).where(Bookmark.id == bookmark_id))
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")
        if payload.collection_id:
            col_result = await session.execute(select(Collection).where(Collection.id == payload.collection_id))
            collection = col_result.scalar_one_or_none()
            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")
        bookmark.collection_id = payload.collection_id
        bookmark.created_at = bookmark.created_at
        await session.flush()
        await session.commit()
        return BookmarkResponse(
            id=bookmark.id,
            resource_type=bookmark.resource_type,
            resource_id=bookmark.resource_id,
            title=bookmark.title,
            metadata=bookmark.metadata_json,
            collection_id=bookmark.collection_id,
            created_at=bookmark.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"move_bookmark error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move bookmark: {str(e)}")


@router.get("/collections", response_model=List[CollectionResponse])
async def list_collections(session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(select(Collection).order_by(Collection.created_at.desc()))
        collections = result.scalars().all()
        return [
            CollectionResponse(id=c.id, name=c.name, created_at=c.created_at)
            for c in collections
        ]
    except Exception as e:
        logger.error(f"list_collections error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load collections: {str(e)}")


@router.post("/collections", response_model=CollectionResponse, status_code=201)
async def create_collection(
    payload: CollectionCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        collection = Collection(id=uuid_str(), name=payload.name)
        session.add(collection)
        await session.flush()
        await session.commit()
        return CollectionResponse(id=collection.id, name=collection.name, created_at=collection.created_at)
    except Exception as e:
        logger.error(f"create_collection error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create collection: {str(e)}")


@router.delete("/collections/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: str,
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await session.execute(select(Collection).where(Collection.id == collection_id))
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        move_stmt = select(Bookmark).where(Bookmark.collection_id == collection_id)
        move_result = await session.execute(move_stmt)
        bookmarks_in_collection = move_result.scalars().all()
        for bm in bookmarks_in_collection:
            bm.collection_id = None
        await session.delete(collection)
        await session.commit()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_collection error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete collection: {str(e)}")
