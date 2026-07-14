import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, JSON, Float, Integer
from datetime import datetime
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./juriscore.db")
# Fallback to sqlite if asyncpg URL not supplied

if DATABASE_URL.startswith("postgresql"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


def uuid_str() -> str:
    return str(uuid.uuid4())


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    title: Mapped[str]
    citation: Mapped[str]
    court: Mapped[str]
    year: Mapped[int]
    subject_tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    full_text: Mapped[str]
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ratio: Mapped[str | None]
    judges: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Statute(Base):
    __tablename__ = "statutes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    title: Mapped[str]
    citation: Mapped[str]
    cap_number: Mapped[str | None]
    full_text: Mapped[str]
    amendments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str]
    email: Mapped[str]
    university: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Notebook(Base):
    __tablename__ = "notebooks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotebookEntry(Base):
    __tablename__ = "notebook_entries"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    notebook_id: Mapped[str] = mapped_column(String, ForeignKey("notebooks.id"))
    case_id: Mapped[str | None] = mapped_column(String, ForeignKey("cases.id"), nullable=True)
    statute_id: Mapped[str | None] = mapped_column(String, ForeignKey("statutes.id"), nullable=True)
    note_text: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FlashcardDeck(Base):
    __tablename__ = "flashcard_decks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    title: Mapped[str]
    subject: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Flashcard(Base):
    __tablename__ = "flashcards"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    deck_id: Mapped[str] = mapped_column(String, ForeignKey("flashcard_decks.id"))
    front: Mapped[str]
    back: Mapped[str]
    interval: Mapped[float] = mapped_column(Float, default=1.0)
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5)
    next_review: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudyNote(Base):
    __tablename__ = "study_notes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    case_id: Mapped[str | None] = mapped_column(String, ForeignKey("cases.id"), nullable=True)
    statute_id: Mapped[str | None] = mapped_column(String, ForeignKey("statutes.id"), nullable=True)
    note_text: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
