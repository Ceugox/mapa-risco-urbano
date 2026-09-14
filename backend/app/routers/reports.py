import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..db import confirm_report, get_reports, insert_report, store_snapshot
from ..netutil import client_ip

router = APIRouter(prefix="/api/reports")
BBOX = (-24.1, -46.9, -23.3, -46.3)
rate: dict[str, deque[float]] = defaultdict(deque)
confirmed: dict[str, set[str]] = defaultdict(set)


class ReportIn(BaseModel):
    category: str
    description: str = Field(max_length=280)
    lat: float
    lon: float

    @field_validator("category")
    @classmethod
    def valid_category(cls, value):
        if value not in {"alagamento", "transito", "clima", "seguranca", "outro"}:
            raise ValueError("categoria inválida")
        return value

    @field_validator("lat", "lon")
    @classmethod
    def valid_coordinate(cls, value, info):
        return value


def _feature(report: dict):
    return {
        "type": "Feature", "id": report["id"],
        "geometry": {"type": "Point", "coordinates": [report["lon"], report["lat"]]},
        "properties": {key: report[key] for key in (
            "id", "category", "description", "created_at", "expires_at", "confirmations", "status", "source"
        )},
    }


@router.post("")
def create_report(data: ReportIn, request: Request):
    if not (BBOX[0] <= data.lat <= BBOX[2] and BBOX[1] <= data.lon <= BBOX[3]):
        raise HTTPException(422, "coordenada fora da área de São Paulo")
    ip = client_ip(request)
    now = time.time()
    while rate[ip] and rate[ip][0] < now - 3600:
        rate[ip].popleft()
    if len(rate[ip]) >= 5:
        raise HTTPException(429, "limite de 5 relatos por hora")
    rate[ip].append(now)
    created = datetime.now(timezone.utc)
    hours = 6 if data.category in {"alagamento", "transito", "clima"} else 24
    report = {
        "id": uuid.uuid4().hex, "category": data.category, "description": data.description,
        "lat": data.lat, "lon": data.lon, "created_at": created.isoformat(),
        "expires_at": (created + timedelta(hours=hours)).isoformat(),
        "confirmations": 0, "status": "visivel", "source": "app",
    }
    insert_report(report)
    store_snapshot("reports", {"type": "FeatureCollection", "features": [_feature(r) for r in get_reports()]})
    return _feature(report)


@router.get("")
def list_reports():
    payload = {"type": "FeatureCollection", "features": [_feature(r) for r in get_reports()]}
    store_snapshot("reports", payload)
    return payload


@router.post("/{report_id}/confirm")
def confirm(report_id: str, request: Request):
    ip = client_ip(request)
    if ip in confirmed[report_id]:
        raise HTTPException(409, "relato já confirmado neste IP")
    value = confirm_report(report_id)
    if value is None:
        raise HTTPException(404, "relato não encontrado")
    confirmed[report_id].add(ip)
    return {"id": report_id, "confirmations": value}
