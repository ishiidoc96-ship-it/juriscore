from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import quote

router = APIRouter()

KENYALAW_SEARCH = "https://www.kenyalaw.org/kl/search/#stq="

def _search_url(query: str) -> str:
    return f"{KENYALAW_SEARCH}{quote(query)}&stp=1"

@router.get("")
async def list_eac_legislation(
    q: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List EAC (East African Community) legislation."""
    eac_laws = [
        {"id": "eac_1", "title": "East African Community Act, 2004", "citation": "EAC Act 2004", "category": "Framework", "status": "In Force", "url": _search_url("East African Community Act 2004")},
        {"id": "eac_2", "title": "EAC Common Market Protocol, 2009", "citation": "Protocol 2009", "category": "Trade", "status": "In Force", "url": _search_url("EAC Common Market Protocol 2009")},
        {"id": "eac_3", "title": "EAC Customs Union Protocol, 2004", "citation": "Protocol 2004", "category": "Trade", "status": "In Force", "url": _search_url("EAC Customs Union Protocol 2004")},
        {"id": "eac_4", "title": "EAC Monetary Union Protocol, 2013", "citation": "Protocol 2013", "category": "Finance", "status": "In Force", "url": _search_url("EAC Monetary Union Protocol 2013")},
        {"id": "eac_5", "title": "EAC Competition Act, 2006", "citation": "Act 2006", "category": "Trade", "status": "In Force", "url": _search_url("EAC Competition Act 2006")},
        {"id": "eac_6", "title": "EAC Investment Act, 2006", "citation": "Act 2006", "category": "Investment", "status": "In Force", "url": _search_url("EAC Investment Act 2006")},
        {"id": "eac_7", "title": "EAC Rules of Origin Regulations, 2015", "citation": "Regulations 2015", "category": "Trade", "status": "In Force", "url": _search_url("EAC Rules of Origin Regulations 2015")},
        {"id": "eac_8", "title": "EAC Non-Tariff Barriers Act, 2012", "citation": "Act 2012", "category": "Trade", "status": "In Force", "url": _search_url("EAC Non-Tariff Barriers Act 2012")},
        {"id": "eac_9", "title": "EAC Sexual and Gender-Based Violence Act, 2016", "citation": "Act 2016", "category": "Human Rights", "status": "In Force", "url": _search_url("EAC Sexual Gender-Based Violence Act 2016")},
        {"id": "eac_10", "title": "EAC Civil Remedies for Victims of Sexual Violence Act, 2018", "citation": "Act 2018", "category": "Human Rights", "status": "In Force", "url": _search_url("EAC Civil Remedies Sexual Violence Act 2018")},
        {"id": "eac_11", "title": "EAC Partner State Accountability Act, 2020", "citation": "Act 2020", "category": "Governance", "status": "In Force", "url": _search_url("EAC Partner State Accountability Act 2020")},
        {"id": "eac_12", "title": "EAC Inter-University Council Charter, 2010", "citation": "Charter 2010", "category": "Education", "status": "In Force", "url": _search_url("EAC Inter-University Council Charter 2010")},
    ]

    if q:
        q_lower = q.lower()
        eac_laws = [l for l in eac_laws if q_lower in l["title"].lower() or q_lower in l["category"].lower()]

    return {"count": len(eac_laws[:limit]), "results": eac_laws[:limit], "source": "juriscore"}


@router.get("/categories/list")
async def list_categories():
    return {"categories": ["Framework", "Trade", "Finance", "Investment", "Human Rights", "Governance", "Education"]}
