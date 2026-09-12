import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..db import get_reports, store_snapshot
from ..ingest import ingest_text
from .reports import _feature

router = APIRouter(prefix="/api/ingest")
rate: dict[str, deque[float]] = defaultdict(deque)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    channel: str = Field(default="manual", max_length=30)


def _refresh_snapshot() -> None:
    store_snapshot("reports", {"type": "FeatureCollection", "features": [_feature(r) for r in get_reports()]})


@router.post("/message")
def ingest_message(data: MessageIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    while rate[ip] and rate[ip][0] < now - 3600:
        rate[ip].popleft()
    if len(rate[ip]) >= 30:
        raise HTTPException(429, "limite de 30 mensagens por hora")
    rate[ip].append(now)
    result = ingest_text(data.text, data.channel)
    if result.get("ingested"):
        _refresh_snapshot()
    return result
