from fastapi import APIRouter, Query
from typing import Optional, List, Dict
from urllib.parse import quote

router = APIRouter()

KENYALAW_SEARCH = "https://www.kenyalaw.org/kl/search/#stq="

def _search_url(query: str) -> str:
    return f"{KENYALAW_SEARCH}{quote(query)}&stp=1"

@router.get("")
async def list_treaties(
    q: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List treaties and international agreements relevant to Kenya."""
    treaties = [
        {"id": "treaty_1", "title": "African Charter on Human and Peoples' Rights", "citation": "Ratified 1991", "category": "Human Rights", "status": "In Force", "url": _search_url("African Charter Human Peoples Rights")},
        {"id": "treaty_2", "title": "International Covenant on Civil and Political Rights (ICCPR)", "citation": "Ratified 1972", "category": "Human Rights", "status": "In Force", "url": _search_url("ICCPR International Covenant Civil Political Rights")},
        {"id": "treaty_3", "title": "International Covenant on Economic, Social and Cultural Rights (ICESCR)", "citation": "Ratified 1972", "category": "Human Rights", "status": "In Force", "url": _search_url("ICESCR International Covenant Economic Social Cultural Rights")},
        {"id": "treaty_4", "title": "Convention on the Elimination of All Forms of Discrimination Against Women (CEDAW)", "citation": "Ratified 1984", "category": "Human Rights", "status": "In Force", "url": _search_url("CEDAW Convention Elimination Discrimination Women")},
        {"id": "treaty_5", "title": "Convention Against Torture (CAT)", "citation": "Ratified 1997", "category": "Human Rights", "status": "In Force", "url": _search_url("Convention Against Torture CAT")},
        {"id": "treaty_6", "title": "African Charter on the Rights and Welfare of the Child", "citation": "Ratified 1999", "category": "Human Rights", "status": "In Force", "url": _search_url("African Charter Rights Welfare Child")},
        {"id": "treaty_7", "title": "Treaty for the Establishment of the East African Community (EAC Treaty)", "citation": "Signed 1999, Amended 2006", "category": "Regional Integration", "status": "In Force", "url": _search_url("East African Community Treaty EAC")},
        {"id": "treaty_8", "title": "Common Market Protocol", "citation": "2009", "category": "Regional Integration", "status": "In Force", "url": _search_url("EAC Common Market Protocol")},
        {"id": "treaty_9", "title": "Customs Union Protocol", "citation": "2004", "category": "Regional Integration", "status": "In Force", "url": _search_url("EAC Customs Union Protocol")},
        {"id": "treaty_10", "title": "Monetary Union Protocol", "citation": "2013", "category": "Regional Integration", "status": "In Force", "url": _search_url("EAC Monetary Union Protocol")},
        {"id": "treaty_11", "title": "United Nations Convention on the Law of the Sea (UNCLOS)", "citation": "Ratified 1982", "category": "Maritime", "status": "In Force", "url": _search_url("UNCLOS United Nations Convention Law Sea")},
        {"id": "treaty_12", "title": "Vienna Convention on Diplomatic Relations", "citation": "Ratified 1964", "category": "Diplomatic", "status": "In Force", "url": _search_url("Vienna Convention Diplomatic Relations")},
        {"id": "treaty_13", "title": "Nairobi Convention (Western Indian Ocean)", "citation": "Ratified 1982", "category": "Environmental", "status": "In Force", "url": _search_url("Nairobi Convention Western Indian Ocean")},
        {"id": "treaty_14", "title": "Paris Agreement on Climate Change", "citation": "Ratified 2016", "category": "Environmental", "status": "In Force", "url": _search_url("Paris Agreement Climate Change")},
        {"id": "treaty_15", "title": "East African Court of Justice Protocol", "citation": "2001", "category": "Regional Integration", "status": "In Force", "url": _search_url("East African Court of Justice Protocol")},
    ]

    if q:
        q_lower = q.lower()
        treaties = [t for t in treaties if q_lower in t["title"].lower() or q_lower in t["category"].lower()]

    return {"count": len(treaties[:limit]), "results": treaties[:limit], "source": "juriscore"}


@router.get("/{treaty_id}")
async def get_treaty(treaty_id: str):
    """Get treaty details."""
    treaties = await list_treaties(limit=100)
    for t in treaties.get("results", []):
        if t["id"] == treaty_id:
            return t
    return {"error": "Treaty not found"}


@router.get("/categories/list")
async def list_categories():
    """List treaty categories."""
    return {
        "categories": [
            "Human Rights",
            "Regional Integration",
            "Environmental",
            "Maritime",
            "Diplomatic",
            "Trade",
            "Labour",
            "Criminal",
        ]
    }
