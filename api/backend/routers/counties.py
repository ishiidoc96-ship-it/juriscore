from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

KENYALAW_BASE = "https://kenyalaw.org/kl"

COUNTIES = [
    {"id": "baringo", "name": "Baringo County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/baringo/"},
    {"id": "bomet", "name": "Bomet County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/bomet/"},
    {"id": "bungoma", "name": "Bungoma County", "region": "Western", "url": f"{KENYALAW_BASE}/county-legislation/bungoma/"},
    {"id": "busia", "name": "Busia County", "region": "Western", "url": f"{KENYALAW_BASE}/county-legislation/busia/"},
    {"id": "elgeyo", "name": "Elgeyo/Marakwet County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/elgeyo-marakwet/"},
    {"id": "embu", "name": "Embu County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/embu/"},
    {"id": "garissa", "name": "Garissa County", "region": "North Eastern", "url": f"{KENYALAW_BASE}/county-legislation/garissa/"},
    {"id": "homa_bay", "name": "Homa Bay County", "region": "Nyanza", "url": f"{KENYALAW_BASE}/county-legislation/homa-bay/"},
    {"id": "isiolo", "name": "Isiolo County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/isiolo/"},
    {"id": "kajiado", "name": "Kajiado County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/kajiado/"},
    {"id": "kakamega", "name": "Kakamega County", "region": "Western", "url": f"{KENYALAW_BASE}/county-legislation/kakamega/"},
    {"id": "kericho", "name": "Kericho County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/kericho/"},
    {"id": "kiambu", "name": "Kiambu County", "region": "Central", "url": f"{KENYALAW_BASE}/county-legislation/kiambu/"},
    {"id": "kilifi", "name": "Kilifi County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/kilifi/"},
    {"id": "kisumu", "name": "Kisumu County", "region": "Nyanza", "url": f"{KENYALAW_BASE}/county-legislation/kisumu/"},
    {"id": "kitui", "name": "Kitui County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/kitui/"},
    {"id": "kwale", "name": "Kwale County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/kwale/"},
    {"id": "laikipia", "name": "Laikipia County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/laikipia/"},
    {"id": "lamu", "name": "Lamu County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/lamu/"},
    {"id": "machakos", "name": "Machakos County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/machakos/"},
    {"id": "makueni", "name": "Makueni County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/makueni/"},
    {"id": "mandera", "name": "Mandera County", "region": "North Eastern", "url": f"{KENYALAW_BASE}/county-legislation/mandera/"},
    {"id": "marsabit", "name": "Marsabit County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/marsabit/"},
    {"id": "meru", "name": "Meru County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/meru/"},
    {"id": "migori", "name": "Migori County", "region": "Nyanza", "url": f"{KENYALAW_BASE}/county-legislation/migori/"},
    {"id": "mombasa", "name": "Mombasa County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/mombasa/"},
    {"id": "muranga", "name": "Murang'a County", "region": "Central", "url": f"{KENYALAW_BASE}/county-legislation/muranga/"},
    {"id": "nairobi", "name": "Nairobi County", "region": "Nairobi", "url": f"{KENYALAW_BASE}/county-legislation/nairobi/"},
    {"id": "nakuru", "name": "Nakuru County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/nakuru/"},
    {"id": "nandi", "name": "Nandi County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/nandi/"},
    {"id": "narok", "name": "Narok County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/narok/"},
    {"id": "nyamira", "name": "Nyamira County", "region": "Nyanza", "url": f"{KENYALAW_BASE}/county-legislation/nyamira/"},
    {"id": "nyandarua", "name": "Nyandarua County", "region": "Central", "url": f"{KENYALAW_BASE}/county-legislation/nyandarua/"},
    {"id": "nyeri", "name": "Nyeri County", "region": "Central", "url": f"{KENYALAW_BASE}/county-legislation/nyeri/"},
    {"id": "samburu", "name": "Samburu County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/samburu/"},
    {"id": "siaya", "name": "Siaya County", "region": "Nyanza", "url": f"{KENYALAW_BASE}/county-legislation/siaya/"},
    {"id": "taita", "name": "Taita/Taveta County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/taita-taveta/"},
    {"id": "tana_river", "name": "Tana River County", "region": "Coast", "url": f"{KENYALAW_BASE}/county-legislation/tana-river/"},
    {"id": "tharaka", "name": "Tharaka-Nithi County", "region": "Eastern", "url": f"{KENYALAW_BASE}/county-legislation/tharaka-nithi/"},
    {"id": "trans_nzoia", "name": "Trans Nzoia County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/trans-nzoia/"},
    {"id": "turkana", "name": "Turkana County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/turkana/"},
    {"id": "uasin_gishu", "name": "Uasin Gishu County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/uasin-gishu/"},
    {"id": "vihiga", "name": "Vihiga County", "region": "Western", "url": f"{KENYALAW_BASE}/county-legislation/vihiga/"},
    {"id": "wajir", "name": "Wajir County", "region": "North Eastern", "url": f"{KENYALAW_BASE}/county-legislation/wajir/"},
    {"id": "west_pokot", "name": "West Pokot County", "region": "Rift Valley", "url": f"{KENYALAW_BASE}/county-legislation/west-pokot/"},
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
