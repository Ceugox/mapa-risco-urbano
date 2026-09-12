import hashlib
import json
import re
import secrets
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .. import db

router = APIRouter(prefix="/api")
rate: dict[str, deque[float]] = defaultdict(deque)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ITERATIONS = 120_000


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), ITERATIONS
    ).hex()


def _throttle(ip: str) -> None:
    now = time.time()
    while rate[ip] and rate[ip][0] < now - 3600:
        rate[ip].popleft()
    if len(rate[ip]) >= 10:
        raise HTTPException(429, "muitas tentativas — tente mais tarde")
    rate[ip].append(now)


def _current_user(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "token ausente")
    user = db.get_user_by_token(authorization.removeprefix("Bearer ").strip())
    if not user:
        raise HTTPException(401, "sessão inválida")
    return user


class Credentials(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(min_length=6, max_length=120)


class ContactsIn(BaseModel):
    contacts: list[dict] = Field(max_length=5)


@router.post("/auth/register")
def register(data: Credentials, request: Request):
    _throttle(request.client.host if request.client else "unknown")
    email = data.email.strip().lower()
    if not EMAIL.match(email):
        raise HTTPException(422, "e-mail inválido")
    salt = secrets.token_hex(16)
    user_id = uuid.uuid4().hex
    if not db.create_user(user_id, email, _hash(data.password, salt), salt):
        raise HTTPException(409, "e-mail já cadastrado")
    token = secrets.token_urlsafe(32)
    db.create_session(token, user_id)
    return {"token": token, "email": email}


@router.post("/auth/login")
def login(data: Credentials, request: Request):
    _throttle(request.client.host if request.client else "unknown")
    user = db.get_user_by_email(data.email.strip().lower())
    if not user or not secrets.compare_digest(
        user["pass_hash"], _hash(data.password, user["salt"])
    ):
        raise HTTPException(401, "e-mail ou senha incorretos")
    token = secrets.token_urlsafe(32)
    db.create_session(token, user["id"])
    return {"token": token, "email": user["email"]}


@router.get("/contacts")
def get_contacts(authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    return {"contacts": json.loads(user["contacts_json"]), "email": user["email"]}


@router.put("/contacts")
def put_contacts(data: ContactsIn, authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    clean = [
        {
            "name": str(item.get("name", ""))[:60],
            "phone": re.sub(r"\D", "", str(item.get("phone", "")))[:15],
        }
        for item in data.contacts
        if str(item.get("name", "")).strip() and re.sub(r"\D", "", str(item.get("phone", "")))
    ]
    db.save_user_contacts(user["id"], json.dumps(clean, ensure_ascii=False))
    return {"ok": True, "contacts": clean}
