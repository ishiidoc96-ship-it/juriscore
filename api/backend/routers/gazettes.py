from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging

logger = logging.getLogger("juriscore")
router = APIRouter()

DEMO_GAZETTES = [
    {
        "id": f"gazette-{i:03d}",
        "title": title,
        "gazette_number": f"GN {num} of {year}",
        "date": f"{year}-{month:02d}-{day:02d}",
        "category": category,
        "county": county,
        "type": gtype,
        "author": author,
        "summary": summary,
        "pages": pages,
        "pdf_url": f"/gazettes/gazette-{i:03d}/pdf",
    }
    for i, (title, num, year, month, day, category, county, gtype, author, summary, pages) in enumerate([
        ("Notice of Intended Settlement of Estate of John Kamau Mwangi", 2241, 2025, 3, 15, "Probate", "Nairobi", "Succession", "High Court of Kenya at Nairobi", "Public notice regarding the intended distribution of the estate of the late John Kamau Mwangi, deceased. All persons having claims against the estate are required to submit them within 30 days.", 2),
        ("Land Acquisition for Construction of Thika Superhighway Extension", 2242, 2025, 3, 18, "Land", "Nairobi", "Acquisition", "National Land Commission", "Compulsory acquisition of parcels of land along the Thika Road corridor for the purposes of road expansion and improvement of the highway infrastructure.", 4),
        ("Environmental Impact Assessment for Mombasa Port Expansion", 2243, 2025, 3, 20, "Environmental", "Mombasa", "Assessment", "National Environment Management Authority", "Notice of public participation meeting for the proposed expansion of Mombasa Port facilities including construction of three new berths.", 3),
        ("Incorporation of East African Digital Fintech Limited", 2244, 2025, 4, 2, "Corporate", "Nairobi", "Incorporation", "Registrar of Companies", "Notice of application for incorporation of East African Digital Fintech Limited and filing of memorandum and articles of association.", 1),
        ("Government Gazette Notice on Minimum Wage Adjustment 2025", 2245, 2025, 4, 5, "Government", "Nairobi", "Regulation", "Ministry of Labour and Social Protection", "Declaration of adjusted minimum wages for all sectors effective 1st May 2025 in accordance with the Wages and Conditions of Employment Act.", 6),
        ("Succession Cause: Estate of Amina Hassan Abdi", 2246, 2025, 4, 10, "Probate", "Mombasa", "Succession", "High Court of Kenya at Mombasa", "Application for grant of letters of administration in respect of the estate of Amina Hassan Abdi, deceased. Interested parties may file objections within 21 days.", 2),
        ("Compulsory Acquisition of Land in Kisumu for Housing Project", 2247, 2025, 4, 12, "Land", "Kisumu", "Acquisition", "County Government of Kisumu", "Notification of compulsory acquisition of 45 acres of land in Kisumu East Sub-County for affordable housing development.", 3),
        ("Public Procurement Notice: Supply of Medical Equipment", 2248, 2025, 4, 15, "Government", "Nakuru", "Tender", "County Government of Nakuru", "Invitation to tender for the supply and delivery of medical equipment to Nakuru County referral hospitals under the Universal Health Coverage programme.", 5),
        ("EIA for Geothermal Power Plant in Olkaria", 2249, 2025, 4, 18, "Environmental", "Nakuru", "Assessment", "Geothermal Development Company", "Public notice on environmental impact assessment for the proposed construction of a 150MW geothermal power generation facility in Olkaria, Naivasha.", 4),
        ("Notice of Strike-Off: Defunct Companies", 2250, 2025, 4, 20, "Corporate", "Nairobi", "Strike-Off", "Registrar of Companies", "Notice of intention to strike off 47 companies from the register for failure to file annual returns for three consecutive years.", 2),
        ("Gazette Notice on Appointment of Chief Administrative Secretary", 2251, 2025, 4, 22, "Government", "Nairobi", "Appointment", "President's Office", "Presidential appointment of Dr. Sarah Njeri Kamau as Chief Administrative Secretary in the Ministry of Education.", 1),
        ("Succession Notice: Estate of Peter Odhiambo Ochieng", 2252, 2025, 4, 25, "Probate", "Kisumu", "Succession", "High Court of Kenya at Kisumu", "Notice to all creditors and claimants against the estate of Peter Odhiambo Ochieng to submit claims within 30 days of this notice.", 2),
        ("Land Dispute Tribunal Decision: Wambua v County Government of Machakos", 2253, 2025, 5, 1, "Land", "Nairobi", "Tribunal", "National Land Commission", "Decision of the National Land Commission on the dispute between James Wambua and the County Government of Machakos regarding compulsory acquisition compensation.", 8),
        ("National Environment Tribunal: Cement Factory Pollution Case", 2254, 2025, 5, 5, "Environmental", "Mombasa", "Tribunal", "National Environment Tribunal", "Ruling on the petition by Mombasa residents against East Africa Portland Cement Company for alleged air and water pollution violations.", 12),
        ("County Government Tender: Road Construction in Eldoret", 2255, 2025, 5, 8, "Government", "Eldoret", "Tender", "County Government of Uasin Gishu", "Open tender for the construction of 25km of all-weather roads in Ainabkoi and Kapseret Sub-Counties under the rural roads programme.", 4),
        ("Incorporation of Rift Valley Agricultural Cooperative Society", 2256, 2025, 5, 10, "Corporate", "Eldoret", "Incorporation", "Registrar of Companies", "Registration notice for Rift Valley Agricultural Cooperative Society Limited as a cooperative society under the Co-operative Societies Act.", 1),
        ("Probate Notice: Estate of Grace Wanjiku Njoroge", 2257, 2025, 5, 12, "Probate", "Nakuru", "Succession", "High Court of Kenya at Nakuru", "Application by Wanjiru Njoroge for grant of probate of the will of Grace Wanjiku Njoroge, deceased. Objections must be filed within 21 days.", 2),
        ("EIA for Lamu Coal Power Project Phase 2", 2258, 2025, 5, 15, "Environmental", "Mombasa", "Assessment", "National Environment Management Authority", "Notice of public scoping exercise for the proposed Phase 2 expansion of the Lamu Coal Power Project and associated transmission infrastructure.", 5),
        ("Government Notice: New Currency Demonetization Directive", 2259, 2025, 5, 18, "Government", "Nairobi", "Regulation", "Central Bank of Kenya", "Directive on the demonetization of old generation KES 1,000 banknotes and exchange timelines for commercial banks across Kenya.", 3),
        ("Land Registry Notice: Digitization of Land Records in Mombasa", 2260, 2025, 5, 20, "Land", "Mombasa", "Registry", "Ministry of Lands and Physical Planning", "Public notice on the ongoing digitization of land registry records in Mombasa County. All landowners are advised to verify their records.", 2),
    ], start=1)
]


class GazetteResponse(BaseModel):
    id: str
    title: str
    gazette_number: str
    date: str
    category: str
    county: str
    type: str
    author: str
    summary: str
    pages: int
    pdf_url: str


class PaginatedGazetteResponse(BaseModel):
    items: List[GazetteResponse]
    total: int
    page: int
    limit: int
    pages: int


@router.get("/", response_model=PaginatedGazetteResponse)
async def list_gazettes(
    q: Optional[str] = Query(None, description="Search in title and summary"),
    category: Optional[str] = Query(None, description="Filter by category"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    county: Optional[str] = Query(None, description="Filter by county"),
    type: Optional[str] = Query(None, description="Filter by gazette type"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    try:
        filtered = DEMO_GAZETTES[:]

        if q:
            ql = q.lower()
            filtered = [g for g in filtered if ql in g["title"].lower() or ql in g["summary"].lower()]

        if category:
            filtered = [g for g in filtered if g["category"].lower() == category.lower()]

        if date:
            filtered = [g for g in filtered if g["date"] == date]

        if county:
            filtered = [g for g in filtered if g["county"].lower() == county.lower()]

        if type:
            filtered = [g for g in filtered if g["type"].lower() == type.lower()]

        total = len(filtered)
        pages_count = max(1, (total + limit - 1) // limit)
        start = (page - 1) * limit
        end = start + limit
        items = filtered[start:end]

        return PaginatedGazetteResponse(
            items=[GazetteResponse(**g) for g in items],
            total=total,
            page=page,
            limit=limit,
            pages=pages_count,
        )
    except Exception as e:
        logger.error(f"list_gazettes error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load gazettes: {str(e)}")


@router.get("/{gazette_id}", response_model=GazetteResponse)
async def get_gazette(gazette_id: str):
    try:
        gazette = next((g for g in DEMO_GAZETTES if g["id"] == gazette_id), None)
        if not gazette:
            raise HTTPException(status_code=404, detail="Gazette notice not found")
        return GazetteResponse(**gazette)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_gazette error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load gazette: {str(e)}")


@router.get("/{gazette_id}/pdf")
async def download_gazette_pdf(gazette_id: str):
    try:
        gazette = next((g for g in DEMO_GAZETTES if g["id"] == gazette_id), None)
        if not gazette:
            raise HTTPException(status_code=404, detail="Gazette notice not found")
        return JSONResponse({
            "status": "placeholder",
            "message": f"PDF download for {gazette['gazette_number']} will be available when real gazette data is integrated.",
            "gazette_id": gazette_id,
            "title": gazette["title"],
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"download_gazette_pdf error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve PDF: {str(e)}")
