from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

KENYALAW_BASE = "https://kenyalaw.org/kl"

@router.get("")
async def list_publications(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List Kenya Law publications."""
    publications = [
        {"id": "pub_1", "title": "Kenya Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/kenya-law-reports/", "description": "Official law reports of Kenya"},
        {"id": "pub_2", "title": "Special Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/special-law-reports/", "description": "Specialised law reports"},
        {"id": "pub_3", "title": "Constitutional and Human Rights Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/constitutional-human-rights/", "description": "Constitutional law reports"},
        {"id": "pub_4", "title": "Commercial Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/commercial-law-reports/", "description": "Commercial law decisions"},
        {"id": "pub_5", "title": "Family Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/family-law-reports/", "description": "Family law decisions"},
        {"id": "pub_6", "title": "Environmental and Land Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/environmental-land/", "description": "Environmental and land law"},
        {"id": "pub_7", "title": "Tax Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/tax-law-reports/", "description": "Tax tribunal decisions"},
        {"id": "pub_8", "title": "Employment and Labour Relations Law Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/employment-labour/", "description": "Employment law decisions"},
        {"id": "pub_9", "title": "Judiciary Newsletters", "type": "Newsletter", "url": f"{KENYALAW_BASE}/publications/newsletters/", "description": "Judiciary newsletters and updates"},
        {"id": "pub_10", "title": "Annual Report of the Judiciary", "type": "Report", "url": f"{KENYALAW_BASE}/publications/annual-report/", "description": "Judiciary annual reports"},
        {"id": "pub_11", "title": "Bench Bulletin", "type": "Bulletin", "url": f"{KENYALAW_BASE}/publications/bench-bulletin/", "description": "Judicial bench bulletins and practice directions"},
        {"id": "pub_12", "title": "Case Digests", "type": "Digests", "url": f"{KENYALAW_BASE}/publications/case-digests/", "description": "Summaries of key judicial decisions"},
        {"id": "pub_13", "title": "Commission Reports", "type": "Reports", "url": f"{KENYALAW_BASE}/publications/commission-reports/", "description": "Law Reform Commission reports"},
        {"id": "pub_14", "title": "Journals", "type": "Journals", "url": f"{KENYALAW_BASE}/publications/journals/", "description": "Legal journals and academic publications"},
        {"id": "pub_15", "title": "Kenya Law News", "type": "News", "url": f"{KENYALAW_BASE}/publications/news/", "description": "Latest news from Kenya Law"},
        {"id": "pub_16", "title": "Law Related Articles", "type": "Articles", "url": f"{KENYALAW_BASE}/articles/", "description": "Legal articles and scholarly writing"},
        {"id": "pub_17", "title": "QMS Quality Policy", "type": "Policy", "url": f"{KENYALAW_BASE}/publications/qms-policy/", "description": "Quality management system policy"},
        {"id": "pub_18", "title": "Service Delivery Charter", "type": "Charter", "url": f"{KENYALAW_BASE}/publications/service-charter/", "description": "Service delivery standards and commitments"},
        {"id": "pub_19", "title": "Strategic Plan", "type": "Plan", "url": f"{KENYALAW_BASE}/publications/strategic-plan/", "description": "Kenya Law strategic plans"},
        {"id": "pub_20", "title": "Weekly Newsletter", "type": "Newsletter", "url": f"{KENYALAW_BASE}/publications/weekly-newsletter/", "description": "Weekly legal updates and summaries"},
    ]

    if q:
        q_lower = q.lower()
        publications = [p for p in publications if q_lower in p["title"].lower() or q_lower in p["description"].lower()]
    if category:
        cat_lower = category.lower()
        publications = [p for p in publications if cat_lower in p["type"].lower()]

    return {"count": len(publications[:limit]), "results": publications[:limit]}


@router.get("/categories/list")
async def list_categories():
    return {"categories": ["Reports", "Newsletter", "Bulletin", "Digests", "Journals", "News", "Articles", "Policy", "Charter", "Plan"]}
