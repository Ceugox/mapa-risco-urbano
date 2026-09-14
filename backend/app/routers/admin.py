import re
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .. import analytics, db
from ..config import settings

router = APIRouter(prefix="/api")
rate: dict[str, deque[float]] = defaultdict(deque)
ADMIN_USER = "__admin__"
EVENT_NAME = re.compile(r"^[a-z][a-z0-9_]{2,40}$")


class AdminLogin(BaseModel):
    password: str = Field(max_length=200)


class EventIn(BaseModel):
    name: str = Field(max_length=40)
    meta: dict = Field(default_factory=dict)


def _throttle(ip: str) -> None:
    now = time.time()
    while rate[ip] and rate[ip][0] < now - 900:
        rate[ip].popleft()
    if len(rate[ip]) >= 5:
        raise HTTPException(429, "muitas tentativas — aguarde 15 minutos")
    rate[ip].append(now)


def require_admin(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "token ausente")
    session = db.get_session(authorization.removeprefix("Bearer ").strip())
    if not session or session["user_id"] != ADMIN_USER:
        raise HTTPException(401, "sessão de admin inválida")
    return True


@router.post("/admin/login")
def login(data: AdminLogin, request: Request):
    if not settings.admin_password:
        raise HTTPException(403, "painel de admin desabilitado (ADMIN_PASSWORD ausente)")
    _throttle(request.client.host if request.client else "unknown")
    if not secrets.compare_digest(data.password.encode(), settings.admin_password.encode()):
        raise HTTPException(401, "senha incorreta")
    token = secrets.token_urlsafe(32)
    db.create_session(token, ADMIN_USER)
    return {"token": token}


@router.get("/admin/stats")
def stats(range: str = "7d", authorization: str | None = Header(default=None)):
    require_admin(authorization)
    analytics.flush()
    try:
        return analytics.stats(range)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/events", status_code=204)
def track(data: EventIn, request: Request):
    if not EVENT_NAME.match(data.name):
        raise HTTPException(422, "nome de evento inválido")
    headers = request.headers
    forwarded = headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    analytics.record(
        analytics.entry(
            method="EVENT", path=data.name, status=0, duration_ms=0, ip=ip,
            user_agent=headers.get("user-agent", ""), referer=str(data.meta.get("referrer", ""))[:200],
        )
    )
