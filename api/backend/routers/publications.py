from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import quote

router = APIRouter()

KENYALAW_SEARCH = "https://www.kenyalaw.org/kl/search/#stq="

def _search_url(query: str) -> str:
    """Build a working KenyaLaw search URL."""
    return f"{KENYALAW_SEARCH}{quote(query)}&stp=1"

@router.get("")
async def list_publications(
    q: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List Kenya Law publications."""
    publications = [
        {"id": "pub_1", "title": "Kenya Law Reports", "type": "Reports", "url": _search_url("Kenya Law Reports"), "description": "Official law reports of Kenya"},
        {"id": "pub_2", "title": "Special Law Reports", "type": "Reports", "url": _search_url("Special Law Reports Kenya"), "description": "Specialised law reports"},
        {"id": "pub_3", "title": "Constitutional and Human Rights Law Reports", "type": "Reports", "url": _search_url("Constitutional Human Rights Reports Kenya"), "description": "Constitutional law reports"},
        {"id": "pub_4", "title": "Commercial Law Reports", "type": "Reports", "url": _search_url("Commercial Law Reports Kenya"), "description": "Commercial law decisions"},
        {"id": "pub_5", "title": "Family Law Reports", "type": "Reports", "url": _search_url("Family Law Reports Kenya"), "description": "Family law decisions"},
        {"id": "pub_6", "title": "Environmental and Land Law Reports", "type": "Reports", "url": _search_url("Environmental Land Law Reports Kenya"), "description": "Environmental and land law"},
        {"id": "pub_7", "title": "Tax Law Reports", "type": "Reports", "url": _search_url("Tax Law Reports Kenya"), "description": "Tax tribunal decisions"},
        {"id": "pub_8", "title": "Employment and Labour Relations Law Reports", "type": "Reports", "url": _search_url("Employment Labour Relations Reports Kenya"), "description": "Employment law decisions"},
        {"id": "pub_9", "title": "Judiciary Newsletters", "type": "Newsletter", "url": _search_url("Judiciary Newsletter Kenya"), "description": "Judiciary newsletters and updates"},
        {"id": "pub_10", "title": "Annual Report of the Judiciary", "type": "Report", "url": _search_url("Judiciary Annual Report Kenya"), "description": "Judiciary annual reports"},
        {"id": "pub_11", "title": "Bench Bulletin", "type": "Bulletin", "url": _search_url("Bench Bulletin Kenya"), "description": "Judicial bench bulletins and practice directions"},
        {"id": "pub_12", "title": "Case Digests", "type": "Digests", "url": _search_url("Case Digests Kenya"), "description": "Summaries of key judicial decisions"},
        {"id": "pub_13", "title": "Commission Reports", "type": "Reports", "url": _search_url("Law Reform Commission Reports Kenya"), "description": "Law Reform Commission reports"},
        {"id": "pub_14", "title": "Journals", "type": "Journals", "url": _search_url("Kenya Law Journal"), "description": "Legal journals and academic publications"},
        {"id": "pub_15", "title": "Kenya Law News", "type": "News", "url": _search_url("Kenya Law News"), "description": "Latest news from Kenya Law"},
        {"id": "pub_16", "title": "Law Related Articles", "type": "Articles", "url": _search_url("Kenya Law Articles"), "description": "Legal articles and scholarly writing"},
        {"id": "pub_17", "title": "QMS Quality Policy", "type": "Policy", "url": _search_url("Kenya Law QMS Quality Policy"), "description": "Quality management system policy"},
        {"id": "pub_18", "title": "Service Delivery Charter", "type": "Charter", "url": _search_url("Kenya Law Service Delivery Charter"), "description": "Service delivery standards and commitments"},
        {"id": "pub_19", "title": "Strategic Plan", "type": "Plan", "url": _search_url("Kenya Law Strategic Plan"), "description": "Kenya Law strategic plans"},
        {"id": "pub_20", "title": "Weekly Newsletter", "type": "Newsletter", "url": _search_url("Kenya Law Weekly Newsletter"), "description": "Weekly legal updates and summaries"},
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
