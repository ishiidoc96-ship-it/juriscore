from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

KENYALAW_BASE = "https://kenyalaw.org/kl"

@router.get("")
async def list_cause_lists(
    q: Optional[str] = Query(None),
    court: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List court cause lists."""
    cause_lists = [
        {"id": "cl_supreme", "court": "Supreme Court", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/supreme-court/", "description": "Cases before the Supreme Court of Kenya"},
        {"id": "cl_appeal", "court": "Court of Appeal", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/court-of-appeal/", "description": "Cases before the Court of Appeal"},
        {"id": "cl_high", "court": "High Court", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/high-court/", "description": "Cases before the High Court of Kenya"},
        {"id": "cl_elrc", "court": "Employment and Labour Relations Court", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/elrc/", "description": "Employment and labour disputes"},
        {"id": "cl_elc", "court": "Environment and Land Court", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/elc/", "description": "Environment and land matters"},
        {"id": "cl_industrial", "court": "Industrial Court", "type": "Superior Courts", "url": f"{KENYALAW_BASE}/cause-lists/industrial-court/", "description": "Industrial court matters"},
        {"id": "cl_cmat", "court": "Communication and Multimedia Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/cmat/", "description": "ICT and communication appeals"},
        {"id": "cl_hivaids", "court": "HIV and AIDS Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/hiv-aids/", "description": "HIV and AIDS related disputes"},
        {"id": "cl_leat", "court": "Legal Education Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/leat/", "description": "Legal education appeals"},
        {"id": "cl_ppdt", "court": "Political Parties Disputes Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/ppdt/", "description": "Political party disputes"},
        {"id": "cl_sdt", "court": "Sports Disputes Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/sdt/", "description": "Sports-related disputes"},
        {"id": "cl_scat", "court": "State Corporations Appeals Tribunal", "type": "Civil and Human Rights Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/scat/", "description": "State corporation appeals"},
        {"id": "cl_bprt", "court": "Business Premises Rent Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/bprt/", "description": "Business premises rent disputes"},
        {"id": "cl_ept", "court": "Energy & Petroleum Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/ept/", "description": "Energy and petroleum matters"},
        {"id": "cl_lat", "court": "Land Acquisition Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/lat/", "description": "Land acquisition disputes"},
        {"id": "cl_net", "court": "National Environment Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/net/", "description": "Environmental matters"},
        {"id": "cl_rrt", "court": "Rent Restriction Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/rrt/", "description": "Rent restriction disputes"},
        {"id": "cl_wat", "court": "Water Appeals Tribunal", "type": "Environment and Land Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/wat/", "description": "Water-related appeals"},
        {"id": "cl_milimani", "court": "Milimani Law Courts", "type": "Subordinate Courts", "url": f"{KENYALAW_BASE}/cause-lists/milimani/", "description": "Milimani commercial and civil divisions"},
        {"id": "cl_kibera", "court": "Kibera Law Courts", "type": "Subordinate Courts", "url": f"{KENYALAW_BASE}/cause-lists/kibera/", "description": "Kibera magistrates court"},
        {"id": "cl_makadara", "court": "Makadara Law Courts", "type": "Subordinate Courts", "url": f"{KENYALAW_BASE}/cause-lists/makadara/", "description": "Makadara magistrates court"},
        {"id": "cl_kscc", "court": "Commercial Division — High Court", "type": "Commercial Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/commercial/", "description": "Commercial disputes and corporate matters"},
        {"id": "cl_admt", "court": "Admiralty Division — High Court", "type": "Commercial Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/admiralty/", "description": "Maritime and admiralty matters"},
        {"id": "cl_ip", "court": "Industrial Property Tribunal", "type": "IP Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/ipt/", "description": "Patents, industrial designs, utility models"},
        {"id": "cl_kipo", "court": "Kenya Industrial Property Institute", "type": "IP Tribunals", "url": f"{KENYALAW_BASE}/cause-lists/kipo/", "description": "Trade marks and intellectual property"},
        {"id": "cl_scc", "court": "Small Claims Court — Nairobi", "type": "Small Claims Court", "url": f"{KENYALAW_BASE}/cause-lists/small-claims/", "description": "Small claims up to Ksh 1 million"},
        {"id": "cl_scc_mombasa", "court": "Small Claims Court — Mombasa", "type": "Small Claims Court", "url": f"{KENYALAW_BASE}/cause-lists/small-claims-mombasa/", "description": "Small claims — Mombasa registry"},
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
