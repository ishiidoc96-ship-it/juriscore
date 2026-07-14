from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr


class CaseSearchFilters(BaseModel):
    q: Optional[str] = None
    court: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    subject: Optional[str] = None
    sort: Optional[str] = None
    limit: int = 20


class CaseResponse(BaseModel):
    id: str
    title: str
    citation: str
    court: str
    year: int
    subject_tags: Optional[List[str]] = None
    summary: Optional[Dict[str, Any]] = None
    ratio: Optional[str] = None
    judges: Optional[List[str]] = None
    created_at: datetime


class CaseComparisonRequest(BaseModel):
    case_a_id: str
    case_b_id: str


class CaseComparisonResponse(BaseModel):
    comparison: Dict[str, Any]


class CaseSaveRequest(BaseModel):
    pass


class StatuteResponse(BaseModel):
    id: str
    title: str
    citation: str
    cap_number: Optional[str] = None
    amendments: Optional[List[Any]] = None
    created_at: datetime


class StatuteSectionsQuery(BaseModel):
    q: Optional[str] = None


class StatuteSearchQuery(BaseModel):
    q: Optional[str] = None
    cap_number: Optional[str] = None


class ConstitutionChapter(BaseModel):
    chapter_num: int
    title: str
    articles: List[int]


class ConstitutionArticle(BaseModel):
    article_num: int
    title: str
    content: str


class NotebookFolderCreate(BaseModel):
    name: str


class NotebookFolderUpdate(BaseModel):
    name: str


class NotebookEntryCreate(BaseModel):
    case_id: Optional[str] = None
    statute_id: Optional[str] = None
    note_text: Optional[str] = None


class NotebookEntryResponse(BaseModel):
    id: str
    notebook_id: str
    case_id: Optional[str] = None
    statute_id: Optional[str] = None
    note_text: Optional[str] = None
    created_at: datetime


class NotebookFolderResponse(BaseModel):
    id: str
    user_id: str
    name: str
    created_at: datetime


class FlashcardDeckCreate(BaseModel):
    title: str
    subject: Optional[str] = None


class FlashcardDeckResponse(BaseModel):
    id: str
    user_id: str
    title: str
    subject: Optional[str] = None
    created_at: datetime


class FlashcardCreate(BaseModel):
    front: str
    back: str


class FlashcardResponse(BaseModel):
    id: str
    deck_id: str
    front: str
    back: str
    interval: float
    ease_factor: float
    next_review: datetime
    created_at: datetime


class FlashcardUpdate(BaseModel):
    interval: float
    ease_factor: float
    next_review: datetime


class StudyNoteCreate(BaseModel):
    case_id: Optional[str] = None
    statute_id: Optional[str] = None
    note_text: str


class StudyNoteUpdate(BaseModel):
    note_text: str


class StudyNoteResponse(BaseModel):
    id: str
    user_id: str
    case_id: Optional[str] = None
    statute_id: Optional[str] = None
    note_text: str
    created_at: datetime
    updated_at: datetime


class GenerateNotesRequest(BaseModel):
    case_id: str


class ExportCaseRequest(BaseModel):
    case_id: str
    format: str


class ExportComparisonRequest(BaseModel):
    case_a_id: str
    case_b_id: str


class ExportStatuteRequest(BaseModel):
    statute_id: str
