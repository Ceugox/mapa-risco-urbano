import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db
from ..netutil import client_ip
from .reports import BBOX

router = APIRouter(prefix="/api/trips")
rate: dict[str, deque[float]] = defaultdict(deque)
DEFAULT_MINUTES = 360
MAX_MINUTES = 720


def _throttle(ip: str) -> None:
    now = time.time()
    while rate[ip] and rate[ip][0] < now - 3600:
        rate[ip].popleft()
    if len(rate[ip]) >= 10:
        raise HTTPException(429, "muitas tentativas — tente mais tarde")
    rate[ip].append(now)


def _inside_bbox(lat: float, lon: float) -> bool:
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]


def _expired(trip) -> bool:
    return trip["expires_at"] < db.now_iso()


def _trip_or_404(trip_id: str):
    trip = db.get_trip(trip_id)
    if not trip:
        raise HTTPException(404, "trajeto não encontrado")
    return trip


def _check_update_token(trip, update_token: str) -> None:
    if not secrets.compare_digest(trip["update_token"], update_token):
        raise HTTPException(403, "token de atualização inválido")


class DestinationIn(BaseModel):
    lat: float
    lon: float
    label: str | None = Field(default=None, max_length=120)


class TripIn(BaseModel):
    destination: DestinationIn
    duration_min: int | None = Field(default=None, ge=1)


class PositionIn(BaseModel):
    lat: float
    lon: float
    update_token: str


class FinishIn(BaseModel):
    update_token: str


@router.post("")
def create_trip(data: TripIn, request: Request):
    if not _inside_bbox(data.destination.lat, data.destination.lon):
        raise HTTPException(422, "destino fora da área de São Paulo")
    _throttle(client_ip(request))
    minutes = min(data.duration_min or DEFAULT_MINUTES, MAX_MINUTES)
    created = datetime.now(timezone.utc)
    expires_at = (created + timedelta(minutes=minutes)).isoformat()
    trip = {
        "id": uuid.uuid4().hex,
        "share_token": secrets.token_urlsafe(24),
        "update_token": secrets.token_urlsafe(24),
        "destination_lat": data.destination.lat,
        "destination_lon": data.destination.lon,
        "destination_label": data.destination.label,
        "created_at": created.isoformat(),
        "expires_at": expires_at,
    }
    db.create_trip(trip)
    return {
        "id": trip["id"],
        "share_token": trip["share_token"],
        "update_token": trip["update_token"],
        "expires_at": expires_at,
    }


@router.post("/{trip_id}/position", status_code=204)
def send_position(trip_id: str, data: PositionIn):
    trip = _trip_or_404(trip_id)
    _check_update_token(trip, data.update_token)
    if trip["finished_at"] or _expired(trip):
        raise HTTPException(410, "trajeto encerrado")
    if not _inside_bbox(data.lat, data.lon):
        raise HTTPException(422, "posição fora da área de São Paulo")
    db.update_trip_position(trip_id, data.lat, data.lon, db.now_iso())


@router.post("/{trip_id}/finish", status_code=204)
def finish_trip(trip_id: str, data: FinishIn):
    trip = _trip_or_404(trip_id)
    _check_update_token(trip, data.update_token)
    db.finish_trip(trip_id)


@router.get("/shared/{share_token}")
def shared_trip(share_token: str):
    trip = db.get_trip_by_share_token(share_token)
    if not trip:
        raise HTTPException(404, "trajeto não encontrado")
    active = not trip["finished_at"] and not _expired(trip)
    last_position = None
    # Depois de encerrado ou expirado, o link deixa de expor onde a pessoa está.
    if active and trip["last_lat"] is not None and trip["last_lon"] is not None:
        last_position = {
            "lat": trip["last_lat"], "lon": trip["last_lon"], "at": trip["last_at"],
        }
    return {
        "destination": {
            "lat": trip["destination_lat"],
            "lon": trip["destination_lon"],
            "label": trip["destination_label"],
        },
        "last_position": last_position,
        "finished_at": trip["finished_at"],
        "expires_at": trip["expires_at"],
        "active": active,
    }
