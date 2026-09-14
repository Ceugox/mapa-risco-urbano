from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..routing import fetch_routes, score_route, time_weights
from .reports import BBOX

router = APIRouter(prefix="/api/route")

SP_TZ = ZoneInfo("America/Sao_Paulo")


class Point(BaseModel):
    lat: float
    lon: float


class RouteIn(BaseModel):
    origin: Point
    destination: Point
    mode: Literal["driving", "walking"] = "driving"
    depart_at: str | None = None


def _inside(point: Point) -> bool:
    return BBOX[0] <= point.lat <= BBOX[2] and BBOX[1] <= point.lon <= BBOX[3]


def _depart_hour(depart_at: str | None) -> int:
    if depart_at is None:
        return datetime.now(SP_TZ).hour
    try:
        parsed = datetime.fromisoformat(depart_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(422, "depart_at inválido; use ISO 8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SP_TZ)
    else:
        parsed = parsed.astimezone(SP_TZ)
    return parsed.hour


@router.post("")
def route(data: RouteIn):
    if not (_inside(data.origin) and _inside(data.destination)):
        raise HTTPException(422, "origem ou destino fora da área de São Paulo")
    depart_hour = _depart_hour(data.depart_at)
    weights = time_weights(data.mode, depart_hour)
    try:
        routes = fetch_routes(
            (data.origin.lat, data.origin.lon),
            (data.destination.lat, data.destination.lon),
            mode=data.mode,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "roteirizador indisponível") from exc
    if not routes:
        raise HTTPException(404, "nenhuma rota encontrada")
    scored = []
    for item in routes[:3]:
        result = score_route(item["coords"], item["distance_m"], weights=weights)
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
        "mode": data.mode,
        "depart_hour": depart_hour,
        "weights": weights,
        "note": (
            "Score relativo por camada (0–100, menor = melhor). Pesos ajustados por "
            "modo e horário: a pé aumenta a exposição a crime e alagamento; à noite "
            "(18h–21h e 22h–5h) o peso do crime sobe. Heurística, não medição. "
            "Trânsito do Google é visual e não entra no cálculo."
        ),
    }
