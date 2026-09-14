"""Registro de acessos sem dados pessoais.

Cada requisição vira uma linha em memória (``buffer``) e é gravada em lote pelo
scheduler. O IP nunca é persistido: vira um hash diário junto com o user-agent,
suficiente para contar visitantes únicos por dia e inútil para reidentificar.
"""

import hashlib
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import settings
from .db import connection

buffer: list[dict] = []
SKIP_PREFIXES = ("/health", "/api/admin", "/api/events")
RANGES = {"24h": (timedelta(hours=24), "hour", 24), "7d": (timedelta(days=7), "day", 7), "30d": (timedelta(days=30), "day", 30)}
PAGE_PATHS = {"/", "/admin", "page_view"}
_HEX_ID = re.compile(r"/[0-9a-f]{8,}(?=/|$)")
_BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|linkedinbot|curl|python-requests|railway", re.IGNORECASE)


def classify_agent(user_agent: str) -> tuple[str, str]:
    ua = user_agent or ""
    if not ua:
        return "unknown", "unknown"
    if _BOTS.search(ua):
        return "bot", "bot"
    device = "mobile" if re.search(r"Mobile|Android|iPhone|iPad", ua) else "desktop"
    if "Edg/" in ua:
        browser = "edge"
    elif "SamsungBrowser" in ua:
        browser = "samsung"
    elif "Firefox/" in ua:
        browser = "firefox"
    elif "Chrome/" in ua or "CriOS/" in ua:
        browser = "chrome"
    elif "Safari/" in ua:
        browser = "safari"
    else:
        browser = "other"
    return device, browser


def visitor_hash(ip: str, user_agent: str, day: str) -> str:
    salt = settings.analytics_salt or "mapasp"
    return hashlib.sha256(f"{salt}|{day}|{ip}|{user_agent}".encode()).hexdigest()[:16]


def referer_host(referer: str) -> str:
    if not referer:
        return ""
    host = urlsplit(referer).netloc.lower()
    return host.removeprefix("www.")


def normalize_path(path: str) -> str:
    path = path.split("?", 1)[0]
    if path.startswith("/assets/"):
        return "/assets/*"
    return _HEX_ID.sub("/{id}", path)


def should_log(path: str) -> bool:
    return not path.startswith(SKIP_PREFIXES)


def entry(*, method: str, path: str, status: int, duration_ms: float, ip: str, user_agent: str, referer: str, ts: str | None = None) -> dict:
    ts = ts or datetime.now(timezone.utc).isoformat()
    device, browser = classify_agent(user_agent)
    return {
        "ts": ts, "method": method, "path": normalize_path(path), "status": status,
        "duration_ms": round(duration_ms, 1), "visitor": visitor_hash(ip, user_agent, ts[:10]),
        "device": device, "browser": browser, "referer": referer_host(referer),
    }


def record(row: dict) -> None:
    buffer.append(row)
    if len(buffer) > 5000:
        del buffer[:1000]


def flush() -> int:
    if not buffer:
        return 0
    rows, buffer[:] = list(buffer), []
    with connection() as conn:
        for row in rows:
            conn.execute(
                """INSERT INTO access_log(ts,method,path,status,duration_ms,visitor,device,browser,referer)
                VALUES(:ts,:method,:path,:status,:duration_ms,:visitor,:device,:browser,:referer)""",
                row,
            )
    return len(rows)


def purge(days: int = 90) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connection() as conn:
        before = conn.execute("SELECT COUNT(*) AS n FROM access_log WHERE ts<?", (cutoff,)).fetchone()["n"]
        conn.execute("DELETE FROM access_log WHERE ts<?", (cutoff,))
    return before


def _bucket(ts: str, unit: str) -> str:
    return ts[:13] if unit == "hour" else ts[:10]


def stats(range_key: str) -> dict:
    if range_key not in RANGES:
        raise ValueError("período inválido")
    span, unit, buckets = RANGES[range_key]
    now = datetime.now(timezone.utc)
    since = (now - span).isoformat()
    with connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT ts,method,path,status,duration_ms,visitor,device,browser,referer FROM access_log WHERE ts>=? ORDER BY ts",
            (since,),
        ).fetchall()]
        users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        reports_total = conn.execute("SELECT COUNT(*) AS n FROM reports").fetchone()["n"]

    events = [r for r in rows if r["method"] == "EVENT"]
    hits = [r for r in rows if r["method"] != "EVENT"]
    pages = [r for r in hits if r["path"] in PAGE_PATHS and r["device"] != "bot"]
    page_ids = {id(r) for r in pages}
    api = [r for r in hits if r["path"].startswith("/api/")]
    errors = [r for r in hits if r["status"] >= 500]
    durations = sorted(r["duration_ms"] for r in api) or [0.0]
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]

    series = []
    step = timedelta(hours=1) if unit == "hour" else timedelta(days=1)
    start = now - step * (buckets - 1)
    by_bucket: dict[str, dict] = {}
    for i in range(buckets):
        key = _bucket((start + step * i).isoformat(), unit)
        by_bucket[key] = {"bucket": key, "requests": 0, "page_views": 0, "visitors": set(), "errors": 0}
    for r in hits:
        slot = by_bucket.get(_bucket(r["ts"], unit))
        if slot is None:
            continue
        slot["requests"] += 1
        if id(r) in page_ids:
            slot["page_views"] += 1
            slot["visitors"].add(r["visitor"])
        if r["status"] >= 500:
            slot["errors"] += 1
    for slot in by_bucket.values():
        slot["visitors"] = len(slot["visitors"])
        series.append(slot)

    def top(counter: Counter, limit: int = 10) -> list[dict]:
        return [{"name": name, "count": count} for name, count in counter.most_common(limit) if name]

    top_paths = [
        {"path": path, "count": count}
        for path, count in Counter(
            r["path"] for r in hits if not r["path"].startswith(("/assets/", "/favicon"))
        ).most_common(12)
    ]
    return {
        "range": range_key,
        "generated_at": now.isoformat(),
        "kpi": {
            "page_views": len(pages),
            "visitors": len({r["visitor"] for r in pages}),
            "api_calls": len(api),
            "errors": len(errors),
            "error_rate": round(len(errors) / len(hits) * 100, 1) if hits else 0.0,
            "p95_ms": round(p95, 1),
            "routes": sum(1 for r in api if r["path"] == "/api/route" and r["method"] == "POST" and r["status"] < 400),
            "reports": sum(1 for r in api if r["path"] == "/api/reports" and r["method"] == "POST" and r["status"] < 400),
            "bots": sum(1 for r in hits if r["device"] == "bot"),
            "users_total": users,
            "reports_total": reports_total,
        },
        "series": series,
        "devices": dict(Counter(r["device"] for r in pages)),
        "browsers": dict(Counter(r["browser"] for r in pages)),
        "referers": top(Counter(r["referer"] for r in pages)),
        "top_paths": top_paths,
        "events": top(Counter(r["path"] for r in events), 20),
        "recent_errors": [
            {"ts": r["ts"], "method": r["method"], "path": r["path"], "status": r["status"]}
            for r in sorted(errors, key=lambda r: r["ts"], reverse=True)[:20]
        ],
    }


class AccessLogMiddleware:
    """ASGI puro: mede a requisição inteira e registra sem tocar no corpo."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not should_log(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_holder = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            headers = {k.decode().lower(): v.decode(errors="ignore") for k, v in scope.get("headers", [])}
            forwarded = headers.get("x-forwarded-for", "")
            client = scope.get("client")
            ip = forwarded.split(",")[0].strip() if forwarded else (client[0] if client else "")
            record(entry(
                method=scope.get("method", ""), path=scope.get("path", ""),
                status=status_holder["status"] or 500,
                duration_ms=(time.perf_counter() - started) * 1000,
                ip=ip, user_agent=headers.get("user-agent", ""), referer=headers.get("referer", ""),
            ))
