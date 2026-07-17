from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import quote

router = APIRouter()

KENYALAW_SEARCH = "https://www.kenyalaw.org/kl/search/#stq="

def _search_url(query: str) -> str:
    return f"{KENYALAW_SEARCH}{quote(query)}&stp=1"

@router.get("")
async def list_cause_lists(
    q: Optional[str] = Query(None),
    court: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List court cause lists."""
    cause_lists = [
        {"id": "cl_supreme", "court": "Supreme Court", "type": "Superior Courts", "url": _search_url("Supreme Court Cause List Kenya"), "description": "Cases before the Supreme Court of Kenya"},
        {"id": "cl_appeal", "court": "Court of Appeal", "type": "Superior Courts", "url": _search_url("Court of Appeal Cause List Kenya"), "description": "Cases before the Court of Appeal"},
        {"id": "cl_high", "court": "High Court", "type": "Superior Courts", "url": _search_url("High Court Cause List Kenya"), "description": "Cases before the High Court of Kenya"},
        {"id": "cl_elrc", "court": "Employment and Labour Relations Court", "type": "Superior Courts", "url": _search_url("Employment Labour Relations Court Cause List"), "description": "Employment and labour disputes"},
        {"id": "cl_elc", "court": "Environment and Land Court", "type": "Superior Courts", "url": _search_url("Environment Land Court Cause List Kenya"), "description": "Environment and land matters"},
        {"id": "cl_industrial", "court": "Industrial Court", "type": "Superior Courts", "url": _search_url("Industrial Court Cause List Kenya"), "description": "Industrial court matters"},
        {"id": "cl_cmat", "court": "Communication and Multimedia Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("Communication Multimedia Appeals Tribunal Kenya"), "description": "ICT and communication appeals"},
        {"id": "cl_hivaids", "court": "HIV and AIDS Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("HIV AIDS Tribunal Kenya"), "description": "HIV and AIDS related disputes"},
        {"id": "cl_leat", "court": "Legal Education Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("Legal Education Appeals Tribunal Kenya"), "description": "Legal education appeals"},
        {"id": "cl_ppdt", "court": "Political Parties Disputes Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("Political Parties Disputes Tribunal Kenya"), "description": "Political party disputes"},
        {"id": "cl_sdt", "court": "Sports Disputes Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("Sports Disputes Tribunal Kenya"), "description": "Sports-related disputes"},
        {"id": "cl_scat", "court": "State Corporations Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": _search_url("State Corporations Appeals Tribunal Kenya"), "description": "State corporation appeals"},
        {"id": "cl_bprt", "court": "Business Premises Rent Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("Business Premises Rent Tribunal Kenya"), "description": "Business premises rent disputes"},
        {"id": "cl_ept", "court": "Energy and Petroleum Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("Energy Petroleum Tribunal Kenya"), "description": "Energy and petroleum matters"},
        {"id": "cl_lat", "court": "Land Acquisition Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("Land Acquisition Tribunal Kenya"), "description": "Land acquisition disputes"},
        {"id": "cl_net", "court": "National Environment Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("National Environment Tribunal Kenya"), "description": "Environmental matters"},
        {"id": "cl_rrt", "court": "Rent Restriction Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("Rent Restriction Tribunal Kenya"), "description": "Rent restriction disputes"},
        {"id": "cl_wat", "court": "Water Appeals Tribunal", "type": "Environment and Land Tribunals", "url": _search_url("Water Appeals Tribunal Kenya"), "description": "Water-related appeals"},
        {"id": "cl_milimani", "court": "Milimani Law Courts", "type": "Subordinate Courts", "url": _search_url("Milimani Law Courts Cause List"), "description": "Milimani commercial and civil divisions"},
        {"id": "cl_kibera", "court": "Kibera Law Courts", "type": "Subordinate Courts", "url": _search_url("Kibera Law Courts Cause List"), "description": "Kibera magistrates court"},
        {"id": "cl_makadara", "court": "Makadara Law Courts", "type": "Subordinate Courts", "url": _search_url("Makadara Law Courts Cause List"), "description": "Makadara magistrates court"},
        {"id": "cl_kscc", "court": "Commercial Division, High Court", "type": "Commercial Tribunals", "url": _search_url("Commercial Division High Court Kenya"), "description": "Commercial disputes and corporate matters"},
        {"id": "cl_admt", "court": "Admiralty Division, High Court", "type": "Commercial Tribunals", "url": _search_url("Admiralty Division High Court Kenya"), "description": "Maritime and admiralty matters"},
        {"id": "cl_ip", "court": "Industrial Property Tribunal", "type": "IP Tribunals", "url": _search_url("Industrial Property Tribunal Kenya"), "description": "Patents, industrial designs, utility models"},
        {"id": "cl_kipo", "court": "Kenya Industrial Property Institute", "type": "IP Tribunals", "url": _search_url("Kenya Industrial Property Institute"), "description": "Trade marks and intellectual property"},
        {"id": "cl_scc", "court": "Small Claims Court, Nairobi", "type": "Small Claims Court", "url": _search_url("Small Claims Court Nairobi Kenya"), "description": "Small claims up to Ksh 1 million"},
        {"id": "cl_scc_mombasa", "court": "Small Claims Court, Mombasa", "type": "Small Claims Court", "url": _search_url("Small Claims Court Mombasa Kenya"), "description": "Small claims, Mombasa registry"},
    ]

    if q:
        q_lower = q.lower()
        cause_lists = [c for c in cause_lists if q_lower in c["court"].lower() or q_lower in c["description"].lower()]
    if court:
        court_lower = court.lower()
        cause_lists = [c for c in cause_lists if court_lower in c["court"].lower()]

    return {"count": len(cause_lists[:limit]), "results": cause_lists[:limit], "total": 9934}


@router.get("/categories/list")
async def list_categories():
    return {
        "categories": [
            "Superior Courts",
            "Civil and Human Rights Tribunals",
            "Environment and Land Tribunals",
            "Subordinate Courts",
            "Commercial Tribunals",
            "IP Tribunals",
            "Small Claims Court",
        ]
    }
