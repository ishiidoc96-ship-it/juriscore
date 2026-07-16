from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import Case, Statute
from models.schemas import ExportCaseRequest, ExportComparisonRequest, ExportStatuteRequest
from core import get_session
import logging
import io

router = APIRouter()


def build_pdf_bytes(title: str, content: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles["Title"]), Paragraph(content.replace("\n", "<br/>"), styles["BodyText"])]
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        return f"{title}\n\n{content}".encode("utf-8")


@router.post("/case-brief")
async def export_case_brief(
    payload: ExportCaseRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Case).where(Case.id == payload.case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    content = case.full_text if payload.format == "full" else (case.summary.get("summary", "").replace("\n", "\n\n") if isinstance(case.summary, dict) else str(case.summary))
    pdf_bytes = build_pdf_bytes(case.title, content)
    from fastapi.responses import Response
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=case_{case.id}.pdf"})


@router.post("/comparison")
async def export_comparison(
    payload: ExportComparisonRequest,
    session: AsyncSession = Depends(get_session),
):
    result_a = await session.execute(select(Case).where(Case.id == payload.case_a_id))
    result_b = await session.execute(select(Case).where(Case.id == payload.case_b_id))
    case_a = result_a.scalar_one_or_none()
    case_b = result_b.scalar_one_or_none()
    if not case_a or not case_b:
        raise HTTPException(status_code=404, detail="Case not found")
    from services.ai_service import compare_cases as ai_compare
    comparison = await ai_compare(case_a.full_text, case_b.full_text)
    content = "\n".join([f"{k}: {v}" for k, v in comparison.items()])
    pdf_bytes = build_pdf_bytes(f"{case_a.title} vs {case_b.title}", content)
    from fastapi.responses import Response
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.post("/statute")
async def export_statute(
    payload: ExportStatuteRequest,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Statute).where(Statute.id == payload.statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=404, detail="Statute not found")
    pdf_bytes = build_pdf_bytes(statute.title, statute.full_text)
    from fastapi.responses import Response
    return Response(content=pdf_bytes, media_type="application/pdf")
