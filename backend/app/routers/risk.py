from fastapi import APIRouter, HTTPException

from ..risk import summarize
from .reports import BBOX

router = APIRouter(prefix="/api/risk")


@router.get("/here")
def here(lat: float, lon: float):
    if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
        raise HTTPException(422, "coordenada fora da área de São Paulo")
    return summarize(lat, lon)
