from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

KENYALAW_BASE = "https://kenyalaw.org/kl"

@router.get("")
async def list_parliament_records(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List parliamentary records, Hansard, and legislation tracker."""
    records = [
        {"id": "par_1", "title": "National Assembly Hansard", "type": "Hansard", "house": "National Assembly", "url": f"{KENYALAW_BASE}/parliament/national-assembly/hansard/", "description": "Official debates of the National Assembly"},
        {"id": "par_2", "title": "Senate Hansard", "type": "Hansard", "house": "Senate", "url": f"{KENYALAW_BASE}/parliament/senate/hansard/", "description": "Official debates of the Senate"},
        {"id": "par_3", "title": "Bills Tracker — National Assembly", "type": "Bills", "house": "National Assembly", "url": f"{KENYALAW_BASE}/parliament/national-assembly/bills/", "description": "Track bills in the National Assembly"},
        {"id": "par_4", "title": "Bills Tracker — Senate", "type": "Bills", "house": "Senate", "url": f"{KENYALAW_BASE}/parliament/senate/bills/", "description": "Track bills in the Senate"},
        {"id": "par_5", "title": "Committees — National Assembly", "type": "Committees", "house": "National Assembly", "url": f"{KENYALAW_BASE}/parliament/national-assembly/committees/", "description": "National Assembly committee reports"},
        {"id": "par_6", "title": "Committees — Senate", "type": "Committees", "house": "Senate", "url": f"{KENYALAW_BASE}/parliament/senate/committees/", "description": "Senate committee reports"},
        {"id": "par_7", "title": "Acts of Parliament", "type": "Legislation", "house": "Both Houses", "url": f"{KENYALAW_BASE}/parliament/acts/", "description": "Enacted Acts of Parliament"},
        {"id": "par_8", "title": "Sessional Papers", "type": "Papers", "house": "Both Houses", "url": f"{KENYALAW_BASE}/parliament/sessional-papers/", "description": "Government sessional papers"},
        {"id": "par_9", "title": "Parliamentary Questions", "type": "Questions", "house": "Both Houses", "url": f"{KENYALAW_BASE}/parliament/questions/", "description": "Parliamentary questions and answers"},
    ]

    if q:
        q_lower = q.lower()
        records = [r for r in records if q_lower in r["title"].lower() or q_lower in r["description"].lower()]
    if category:
        cat_lower = category.lower()
        records = [r for r in records if cat_lower in r["type"].lower()]

    return {"count": len(records[:limit]), "results": records[:limit]}


@router.get("/categories/list")
async def list_categories():
    return {"categories": ["Hansard", "Bills", "Committees", "Legislation", "Papers", "Questions"]}
