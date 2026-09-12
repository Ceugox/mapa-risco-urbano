from fastapi import APIRouter, HTTPException

from ..support import nearby
from .reports import BBOX

router = APIRouter(prefix="/api/support")


@router.get("/nearby")
def support_nearby(lat: float, lon: float, limit: int = 12):
    if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
        raise HTTPException(422, "coordenada fora da área de São Paulo")
    return {"points": nearby(lat, lon, min(limit, 20))}
