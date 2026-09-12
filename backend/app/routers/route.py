import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..routing import fetch_routes, score_route
from .reports import BBOX

router = APIRouter(prefix="/api/route")


class Point(BaseModel):
    lat: float
    lon: float


class RouteIn(BaseModel):
    origin: Point
    destination: Point


def _inside(point: Point) -> bool:
    return BBOX[0] <= point.lat <= BBOX[2] and BBOX[1] <= point.lon <= BBOX[3]


@router.post("")
def route(data: RouteIn):
    if not (_inside(data.origin) and _inside(data.destination)):
        raise HTTPException(422, "origem ou destino fora da área de São Paulo")
    try:
        routes = fetch_routes(
            (data.origin.lat, data.origin.lon), (data.destination.lat, data.destination.lon)
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "roteirizador indisponível") from exc
    if not routes:
        raise HTTPException(404, "nenhuma rota encontrada")
    scored = []
    for item in routes[:3]:
        result = score_route(item["coords"], item["distance_m"])
        scored.append({
            "distance_km": round(item["distance_m"] / 1000, 1),
            "duration_min": round(item["duration_s"] / 60),
            "score": result["score"],
            "level": result["level"],
            "breakdown": result["breakdown"],
            "geometry": {"type": "LineString", "coordinates": item["coords"]},
        })
    scored.sort(key=lambda item: item["score"])
    return {
        "routes": scored,
        "note": "Score relativo por camada (0–100, menor = melhor). Trânsito do Google é visual e não entra no cálculo.",
    }
