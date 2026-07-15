from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()

DEMO_TRIBUNALS = [
    {
        "id": f"trib-{i:03d}",
        "title": title,
        "citation": citation,
        "tribunal_type": ttype,
        "tribunal_name": tname,
        "date": date,
        "year": year,
        "parties": parties,
        "subject": subject,
        "summary": summary,
        "outcome": outcome,
        "presiding_officer": presiding,
    }
    for i, (title, citation, ttype, tname, date, year, parties, subject, summary, outcome, presiding) in enumerate([
        ("Kenya Revenue Authority v James Mwangi Transporters Ltd", "TAT Appeal No. 142 of 2024", "TAT", "Tax Appeals Tribunal", "2025-01-15", 2025, "Kenya Revenue Authority v James Mwangi Transporters Limited", "Tax Assessment", "Appeal against assessment of corporation tax for the years 2019-2022. The Appellant contested the Respondent's determination of taxable income.", "Appeal partially allowed. Assessment reduced by 30%.", "Hon. Lady Justice Ruth Sitati"),
        ("National Environment Tribunal v Kajiado County Government", "NET Cause No. 87 of 2024", "NET", "National Environment Tribunal", "2025-01-22", 2025, "Residents of Kajiado South v Kajiado County Government", "Environmental Law", "Challenge to the approval of a waste processing facility near residential areas without adequate public participation.", "Petition allowed. Approval quashed for failure to conduct public participation.", "Dr. Michael Okoth"),
        ("John Kiprotich v Attorney General", "BPRT Case No. 56 of 2024", "BPRT", "Business Premises Rent Tribunal", "2025-02-03", 2025, "John Kiprotich v Attorney General", "Landlord-Tenant Dispute", "Dispute over rental increment for government-owned commercial premises in Eldoret CBD.", "Rent increase capped at 8% per annum for three years.", "Hon. Mwaura Kabiru"),
        ("Procurement Authority v Skyward Construction Co Ltd", "PPRA Complaint No. 203 of 2024", "PPRA", "Public Procurement Regulatory Authority", "2025-02-10", 2025, "National Construction Authority v Skyward Construction Company Limited", "Public Procurement", "Complaint regarding irregular award of KES 2.5 billion road construction tender in Mombasa County.", "Complaint upheld. Tender award annulled and re-tendering ordered.", "Chairperson Mrs. Agnes Mwangi"),
        ("Jane Wanjiru v Kenya Meat Processors Association", "NET Cause No. 112 of 2024", "NET", "National Environment Tribunal", "2025-02-18", 2025, "Jane Wanjiku Muthoni v Kenya Meat Processors Association", "Employment Law", "Claim for unfair termination and unpaid statutory benefits by a former quality assurance officer.", "Claimant awarded 12 months' salary as compensation plus unpaid benefits.", "Hon. James Odhiambo"),
        ("Kenya Airways PLC v Commissioner of Domestic Taxes", "TAT Appeal No. 89 of 2024", "TAT", "Tax Appeals Tribunal", "2025-03-05", 2025, "Kenya Airways PLC v Commissioner of Domestic Taxes", "Tax Law", "Appeal against withholding tax assessment on international flight crew allowances.", "Appeal dismissed. Withholding tax properly assessed.", "Hon. Lady Justice Abigail Mwangi"),
        ("Mombasa Port Workers Union v Kenya Ports Authority", "NET Cause No. 45 of 2025", "NET", "National Environment Tribunal", "2025-03-12", 2025, "Mombasa Port Workers Union v Kenya Ports Authority", "Employment Law", "Dispute over collective bargaining agreement and proposed changes to shift allowances.", "CBA renegotiation ordered. No changes to existing allowances for 24 months.", "Hon. Peter Njoroge"),
        ("Green Savanna Holdings v Kisumu County Government", "BPRT Case No. 78 of 2024", "BPRT", "Business Premises Rent Tribunal", "2025-03-20", 2025, "Green Savanna Holdings Limited v Kisumu County Government", "Landlord-Tenant Dispute", "Eviction suit by commercial landlord against county government for non-payment of rent for 18 months.", "Stay of eviction granted. County government ordered to pay arrears within 60 days.", "Hon. Mwaura Kabiru"),
        ("Public Service Alliance v National Treasury", "PPRA Complaint No. 178 of 2024", "PPRA", "Public Procurement Regulatory Authority", "2025-04-02", 2025, "Public Service Alliance v National Treasury", "Public Procurement", "Challenge to the sole-sourcing of a KES 800 million ICT system upgrade without competitive bidding.", "Complaint dismissed. Sole-sourcing justified under emergency provisions.", "Chairperson Mrs. Agnes Mwangi"),
        ("Peter Otieno v Digital Solutions Kenya Ltd", "NET Cause No. 67 of 2025", "NET", "National Environment Tribunal", "2025-04-10", 2025, "Peter Otieno Odhiambo v Digital Solutions Kenya Limited", "Employment Law", "Claim for wrongful dismissal and denial of earned commissions on software sales.", "Claimant awarded 6 months' salary and unpaid commissions of KES 340,000.", "Hon. James Odhiambo"),
        ("Commissioner of Insurance v Pan Africa Life Assurance", "TAT Appeal No. 201 of 2024", "TAT", "Tax Appeals Tribunal", "2025-04-18", 2025, "Commissioner of Insurance v Pan Africa Life Assurance Limited", "Insurance Tax", "Appeal regarding the taxability of reinsurance reserves held offshore.", "Appeal allowed. Reserves exempt from corporation tax under the Insurance Act.", "Hon. Lady Justice Ruth Sitati"),
        ("Nairobi Traders Association v Nairobi City County", "BPRT Case No. 134 of 2025", "BPRT", "Business Premises Rent Tribunal", "2025-05-06", 2025, "Nairobi Traders Association v Nairobi City County Government", "Landlord-Tenant Dispute", "Class action by 200+ market traders against proposed rent increment of 40% at Wakulima Market.", "Rent increment reduced to 12% phased over two years.", "Hon. Peter Njoroge"),
        ("Wetlands Conservation Group v National Environment Authority", "NET Cause No. 23 of 2025", "NET", "National Environment Tribunal", "2025-05-14", 2025, "Wetlands Conservation Group of Kenya v National Environment Management Authority", "Environmental Law", "Application to stop construction of a resort hotel on protected wetlands in Lamu.", "Injunction granted. Construction halted pending full environmental assessment.", "Dr. Michael Okoth"),
        ("Rift Valley Dairy Farmers v Commissioner of Taxes", "TAT Appeal No. 156 of 2025", "TAT", "Tax Appeals Tribunal", "2025-05-22", 2025, "Rift Valley Dairy Farmers Cooperative Society v Commissioner of Domestic Taxes", "Tax Law", "Appeal against withholding tax on milk payments to smallholder farmers.", "Appeal allowed. Cooperative societies exempt from withholding tax on member payments.", "Hon. Lady Justice Abigail Mwangi"),
        ("County Health Workers Union v Nakuru County Government", "PPRA Complaint No. 112 of 2025", "PPRA", "Public Procurement Regulatory Authority", "2025-06-01", 2025, "County Health Workers Union v Nakuru County Government", "Public Procurement", "Complaint regarding procurement of pharmaceutical supplies without following proper tendering procedures.", "Complaint upheld. Procurement process found irregular and new tender ordered.", "Chairperson Mrs. Agnes Mwangi"),
    ], start=1)
]


class TribunalResponse(BaseModel):
    id: str
    title: str
    citation: str
    tribunal_type: str
    tribunal_name: str
    date: str
    year: int
    parties: str
    subject: str
    summary: str
    outcome: str
    presiding_officer: str


class PaginatedTribunalResponse(BaseModel):
    items: List[TribunalResponse]
    total: int
    page: int
    limit: int
    pages: int


@router.get("/", response_model=PaginatedTribunalResponse)
async def list_tribunals(
    types: Optional[str] = Query(None, description="Comma-separated tribunal types: NET, TAT, BPRT, PPRA"),
    year: Optional[int] = Query(None, description="Filter by year"),
    q: Optional[str] = Query(None, description="Search in title, parties, subject, summary"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    try:
        filtered = DEMO_TRIBUNALS[:]

        if types:
            type_list = [t.strip().upper() for t in types.split(",")]
            filtered = [d for d in filtered if d["tribunal_type"] in type_list]

        if year:
            filtered = [d for d in filtered if d["year"] == year]

        if q:
            ql = q.lower()
            filtered = [
                d for d in filtered
                if ql in d["title"].lower()
                or ql in d["parties"].lower()
                or ql in d["subject"].lower()
                or ql in d["summary"].lower()
            ]

        total = len(filtered)
        pages_count = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit
        items = filtered[start:end]

        return PaginatedTribunalResponse(
            items=[TribunalResponse(**d) for d in items],
            total=total,
            page=page,
            limit=limit,
            pages=pages_count,
        )
    except Exception as e:
        logger.error(f"list_tribunals error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load tribunal decisions: {str(e)}")


@router.get("/{decision_id}", response_model=TribunalResponse)
async def get_tribunal_decision(decision_id: str):
    try:
        decision = next((d for d in DEMO_TRIBUNALS if d["id"] == decision_id), None)
        if not decision:
            raise HTTPException(status_code=404, detail="Tribunal decision not found")
        return TribunalResponse(**decision)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_tribunal_decision error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load decision: {str(e)}")
