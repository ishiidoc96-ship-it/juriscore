import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, JSON, Float, Integer
from datetime import datetime
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Use /tmp for Vercel serverless (writable), or local dir for dev
    import tempfile
    _db_dir = tempfile.gettempdir()
    DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(_db_dir, 'juriscore.db')}"

if DATABASE_URL.startswith("postgresql://"):
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
    full_text: Mapped[str] = mapped_column(String, default="")
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
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    salt: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)


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


class SearchHistory(Base):
    __tablename__ = "search_history"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    query: Mapped[str]
    jurisdiction: Mapped[str] = mapped_column(String, default="kenya")
    doc_type: Mapped[str | None]
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
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


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    title: Mapped[str]
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkspaceCase(Base):
    __tablename__ = "workspace_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"))
    case_id: Mapped[str] = mapped_column(String, ForeignKey("cases.id"))
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceAct(Base):
    __tablename__ = "workspace_acts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"))
    act_id: Mapped[str] = mapped_column(String, ForeignKey("statutes.id"))
    section: Mapped[str] = mapped_column(String, default="")
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceNote(Base):
    __tablename__ = "workspace_notes"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"))
    title: Mapped[str]
    content: Mapped[str] = mapped_column(String, default="")
    color: Mapped[str] = mapped_column(String, default="#ffffff")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceFile(Base):
    __tablename__ = "workspace_files"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"))
    name: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mime_type: Mapped[str] = mapped_column(String, default="application/octet-stream")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceActivity(Base):
    __tablename__ = "workspace_activity"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"))
    type: Mapped[str]
    title: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


from sqlalchemy import Index

Index("ix_cases_title", Case.title)
Index("ix_cases_court", Case.court)
Index("ix_cases_year", Case.year)
Index("ix_statutes_title", Statute.title)
Index("ix_notebook_folders_user", Notebook.user_id)
Index("ix_notebook_entries_notebook", NotebookEntry.notebook_id)
Index("ix_flashcard_decks_user", FlashcardDeck.user_id)
Index("ix_flashcards_deck", Flashcard.deck_id)
Index("ix_study_notes_user", StudyNote.user_id)
Index("ix_study_notes_case", StudyNote.case_id)
Index("ix_search_history_user", SearchHistory.user_id)
Index("ix_search_history_created", SearchHistory.created_at)
Index("ix_bookmarks_user", Bookmark.user_id)
Index("ix_bookmarks_resource", Bookmark.resource_type, Bookmark.resource_id)
Index("ix_workspace_cases_workspace", WorkspaceCase.workspace_id)
Index("ix_workspace_acts_workspace", WorkspaceAct.workspace_id)
Index("ix_workspace_notes_workspace", WorkspaceNote.workspace_id)
Index("ix_workspace_files_workspace", WorkspaceFile.workspace_id)
Index("ix_workspace_activity_workspace", WorkspaceActivity.workspace_id)


# --- KenyaLaw Local Database (cached from live searches) ---
class KenyaLawCase(Base):
    __tablename__ = "kenyalaw_cases"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    citation: Mapped[str] = mapped_column(String, default="")
    court: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int] = mapped_column(Integer, default=0)
    doc_type: Mapped[str] = mapped_column(String, default="judgment")
    excerpt: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    search_url: Mapped[str] = mapped_column(String, default="")
    topics: Mapped[list | None] = mapped_column(JSON, nullable=True)
    judges: Mapped[list | None] = mapped_column(JSON, nullable=True)
    case_number: Mapped[str] = mapped_column(String, default="")
    full_text: Mapped[str] = mapped_column(String, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    last_synced: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class KenyaLawLegislation(Base):
    __tablename__ = "kenyalaw_legislation"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    citation: Mapped[str] = mapped_column(String, default="")
    act_number: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int] = mapped_column(Integer, default=0)
    doc_type: Mapped[str] = mapped_column(String, default="legislation")
    excerpt: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    full_text: Mapped[str] = mapped_column(String, default="")
    last_synced: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class KenyaLawArticle(Base):
    __tablename__ = "kenyalaw_articles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str]
    author: Mapped[str] = mapped_column(String, default="")
    date: Mapped[str] = mapped_column(String, default="")
    doc_type: Mapped[str] = mapped_column(String, default="article")
    excerpt: Mapped[str] = mapped_column(String, default="")
    url: Mapped[str] = mapped_column(String, default="")
    full_text: Mapped[str] = mapped_column(String, default="")
    last_synced: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SearchCache(Base):
    __tablename__ = "search_cache"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    query_hash: Mapped[str] = mapped_column(String, index=True)
    query_text: Mapped[str] = mapped_column(String)
    results_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class SyncStatus(Base):
    __tablename__ = "sync_status"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    last_sync: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    total_legislation: Mapped[int] = mapped_column(Integer, default=0)
    total_articles: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="idle")
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


Index("ix_kenyalaw_cases_title", KenyaLawCase.title)
Index("ix_kenyalaw_cases_court", KenyaLawCase.court)
Index("ix_kenyalaw_cases_year", KenyaLawCase.year)
Index("ix_kenyalaw_cases_doc_type", KenyaLawCase.doc_type)
Index("ix_kenyalaw_legislation_title", KenyaLawLegislation.title)
Index("ix_kenyalaw_articles_title", KenyaLawArticle.title)
Index("ix_search_cache_query_hash", SearchCache.query_hash)
Index("ix_search_cache_expires", SearchCache.expires_at)
