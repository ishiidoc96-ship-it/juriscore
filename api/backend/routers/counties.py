from fastapi import APIRouter, Query
from typing import Optional
from urllib.parse import quote

router = APIRouter()

KENYALAW_SEARCH = "https://www.kenyalaw.org/kl/search/#stq="

def _search_url(query: str) -> str:
    return f"{KENYALAW_SEARCH}{quote(query)}&stp=1"

COUNTIES = [
    {"id": "baringo", "name": "Baringo County", "region": "Rift Valley", "county_seat": "Kabarnet", "url": _search_url("Baringo County Legislation")},
    {"id": "bomet", "name": "Bomet County", "region": "Rift Valley", "county_seat": "Bomet", "url": _search_url("Bomet County Legislation")},
    {"id": "bungoma", "name": "Bungoma County", "region": "Western", "county_seat": "Bungoma", "url": _search_url("Bungoma County Legislation")},
    {"id": "busia", "name": "Busia County", "region": "Western", "county_seat": "Busia", "url": _search_url("Busia County Legislation")},
    {"id": "elgeyo", "name": "Elgeyo/Marakwet County", "region": "Rift Valley", "county_seat": "Iten", "url": _search_url("Elgeyo Marakwet County Legislation")},
    {"id": "embu", "name": "Embu County", "region": "Eastern", "county_seat": "Embu", "url": _search_url("Embu County Legislation")},
    {"id": "garissa", "name": "Garissa County", "region": "North Eastern", "county_seat": "Garissa", "url": _search_url("Garissa County Legislation")},
    {"id": "homa_bay", "name": "Homa Bay County", "region": "Nyanza", "county_seat": "Homa Bay", "url": _search_url("Homa Bay County Legislation")},
    {"id": "isiolo", "name": "Isiolo County", "region": "Eastern", "county_seat": "Isiolo", "url": _search_url("Isiolo County Legislation")},
    {"id": "kajiado", "name": "Kajiado County", "region": "Rift Valley", "county_seat": "Kajiado", "url": _search_url("Kajiado County Legislation")},
    {"id": "kakamega", "name": "Kakamega County", "region": "Western", "county_seat": "Kakamega", "url": _search_url("Kakamega County Legislation")},
    {"id": "kericho", "name": "Kericho County", "region": "Rift Valley", "county_seat": "Kericho", "url": _search_url("Kericho County Legislation")},
    {"id": "kiambu", "name": "Kiambu County", "region": "Central", "county_seat": "Kiambu", "url": _search_url("Kiambu County Legislation")},
    {"id": "kilifi", "name": "Kilifi County", "region": "Coast", "county_seat": "Kilifi", "url": _search_url("Kilifi County Legislation")},
    {"id": "kisumu", "name": "Kisumu County", "region": "Nyanza", "county_seat": "Kisumu", "url": _search_url("Kisumu County Legislation")},
    {"id": "kitui", "name": "Kitui County", "region": "Eastern", "county_seat": "Kitui", "url": _search_url("Kitui County Legislation")},
    {"id": "kwale", "name": "Kwale County", "region": "Coast", "county_seat": "Kwale", "url": _search_url("Kwale County Legislation")},
    {"id": "laikipia", "name": "Laikipia County", "region": "Rift Valley", "county_seat": "Nanyuki", "url": _search_url("Laikipia County Legislation")},
    {"id": "lamu", "name": "Lamu County", "region": "Coast", "county_seat": "Lamu", "url": _search_url("Lamu County Legislation")},
    {"id": "machakos", "name": "Machakos County", "region": "Eastern", "county_seat": "Machakos", "url": _search_url("Machakos County Legislation")},
    {"id": "makueni", "name": "Makueni County", "region": "Eastern", "county_seat": "Wote", "url": _search_url("Makueni County Legislation")},
    {"id": "mandera", "name": "Mandera County", "region": "North Eastern", "county_seat": "Mandera", "url": _search_url("Mandera County Legislation")},
    {"id": "marsabit", "name": "Marsabit County", "region": "Eastern", "county_seat": "Marsabit", "url": _search_url("Marsabit County Legislation")},
    {"id": "meru", "name": "Meru County", "region": "Eastern", "county_seat": "Meru", "url": _search_url("Meru County Legislation")},
    {"id": "migori", "name": "Migori County", "region": "Nyanza", "county_seat": "Migori", "url": _search_url("Migori County Legislation")},
    {"id": "mombasa", "name": "Mombasa County", "region": "Coast", "county_seat": "Mombasa", "url": _search_url("Mombasa County Legislation")},
    {"id": "muranga", "name": "Murang'a County", "region": "Central", "county_seat": "Murang'a", "url": _search_url("Muranga County Legislation")},
    {"id": "nairobi", "name": "Nairobi County", "region": "Nairobi", "county_seat": "Nairobi", "url": _search_url("Nairobi County Legislation")},
    {"id": "nakuru", "name": "Nakuru County", "region": "Rift Valley", "county_seat": "Nakuru", "url": _search_url("Nakuru County Legislation")},
    {"id": "nandi", "name": "Nandi County", "region": "Rift Valley", "county_seat": "Kapsabet", "url": _search_url("Nandi County Legislation")},
    {"id": "narok", "name": "Narok County", "region": "Rift Valley", "county_seat": "Narok", "url": _search_url("Narok County Legislation")},
    {"id": "nyamira", "name": "Nyamira County", "region": "Nyanza", "county_seat": "Nyamira", "url": _search_url("Nyamira County Legislation")},
    {"id": "nyandarua", "name": "Nyandarua County", "region": "Central", "county_seat": "Ol Kalou", "url": _search_url("Nyandarua County Legislation")},
    {"id": "nyeri", "name": "Nyeri County", "region": "Central", "county_seat": "Nyeri", "url": _search_url("Nyeri County Legislation")},
    {"id": "samburu", "name": "Samburu County", "region": "Rift Valley", "county_seat": "Maralal", "url": _search_url("Samburu County Legislation")},
    {"id": "siaya", "name": "Siaya County", "region": "Nyanza", "county_seat": "Siaya", "url": _search_url("Siaya County Legislation")},
    {"id": "taita", "name": "Taita/Taveta County", "region": "Coast", "county_seat": "Mwatate", "url": _search_url("Taita Taveta County Legislation")},
    {"id": "tana_river", "name": "Tana River County", "region": "Coast", "county_seat": "Hola", "url": _search_url("Tana River County Legislation")},
    {"id": "tharaka", "name": "Tharaka-Nithi County", "region": "Eastern", "county_seat": "Chuka", "url": _search_url("Tharaka Nithi County Legislation")},
    {"id": "trans_nzoia", "name": "Trans Nzoia County", "region": "Rift Valley", "county_seat": "Kitale", "url": _search_url("Trans Nzoia County Legislation")},
    {"id": "turkana", "name": "Turkana County", "region": "Rift Valley", "county_seat": "Lodwar", "url": _search_url("Turkana County Legislation")},
    {"id": "uasin_gishu", "name": "Uasin Gishu County", "region": "Rift Valley", "county_seat": "Eldoret", "url": _search_url("Uasin Gishu County Legislation")},
    {"id": "vihiga", "name": "Vihiga County", "region": "Western", "county_seat": "Mbale", "url": _search_url("Vihiga County Legislation")},
    {"id": "wajir", "name": "Wajir County", "region": "North Eastern", "county_seat": "Wajir", "url": _search_url("Wajir County Legislation")},
    {"id": "west_pokot", "name": "West Pokot County", "region": "Rift Valley", "county_seat": "Kapenguria", "url": _search_url("West Pokot County Legislation")},
]


@router.get("")
async def list_counties(
    q: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """List all 47 counties with legislative information."""
    counties = COUNTIES
    if q:
        q_lower = q.lower()
        counties = [c for c in counties if q_lower in c["name"].lower()]
    if region:
        region_lower = region.lower()
        counties = [c for c in counties if region_lower in c["region"].lower()]
    return {"count": len(counties), "results": counties[:limit], "total_counties": 47}


@router.get("/regions/list")
async def list_regions():
    return {"regions": ["Rift Valley", "Western", "Eastern", "Nyanza", "Central", "Coast", "North Eastern", "Nairobi"]}


@router.get("/{county_id}")
async def get_county(county_id: str):
    for c in COUNTIES:
        if c["id"] == county_id:
            return c
    return {"error": "County not found"}
