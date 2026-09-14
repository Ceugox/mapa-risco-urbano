import json
import math
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .config import settings

_NAMED = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _postgres() -> bool:
    return settings.database_url.startswith(("postgres://", "postgresql://"))


def _path() -> Path:
    path = Path(settings.database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _translate(sql: str) -> str:
    return _NAMED.sub(r"%(\1)s", sql).replace("?", "%s")


class _PgConnection:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params=()):
        return self._conn.execute(_translate(sql), params)

    def executescript(self, script: str):
        return self._conn.execute(script)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


@contextmanager
def connection():
    if _postgres():
        conn = _PgConnection(psycopg.connect(settings.database_url, row_factory=dict_row))
    else:
        conn = sqlite3.connect(_path())
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS layer_snapshots (
                layer TEXT PRIMARY KEY, fetched_at TEXT NOT NULL,
                source_updated_at TEXT, payload_json TEXT NOT NULL,
                ok INTEGER NOT NULL, error TEXT
            );
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY, category TEXT NOT NULL, description TEXT NOT NULL,
                lat REAL NOT NULL, lon REAL NOT NULL, created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL, confirmations INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS geocode_cache (
                key TEXT PRIMARY KEY, lat REAL, lon REAL, precision TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                pass_hash TEXT NOT NULL, salt TEXT NOT NULL,
                contacts_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, user_id TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS access_log (
                ts TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL,
                status INTEGER NOT NULL, duration_ms REAL NOT NULL, visitor TEXT NOT NULL,
                device TEXT NOT NULL, browser TEXT NOT NULL, referer TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS access_log_ts ON access_log(ts);
            CREATE TABLE IF NOT EXISTS flood_history (
                key TEXT NOT NULL, name TEXT, lat REAL NOT NULL, lon REAL NOT NULL,
                seen_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS flood_history_key_seen ON flood_history(key, seen_at);
            """
        )
        if _postgres():
            rows = conn.execute(
                "SELECT column_name AS name FROM information_schema.columns"
                " WHERE table_name='reports'"
            ).fetchall()
        else:
            rows = conn.execute("PRAGMA table_info(reports)").fetchall()
        columns = [row["name"] for row in rows]
        if "source" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN source TEXT NOT NULL DEFAULT 'app'")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def store_snapshot(
    layer: str,
    payload: dict,
    ok: bool = True,
    error: str | None = None,
    source_updated_at: str | None = None,
) -> None:
    with connection() as conn:
        previous = conn.execute(
            "SELECT payload_json, source_updated_at FROM layer_snapshots WHERE layer=?",
            (layer,),
        ).fetchone()
        if not ok and previous:
            payload_json = previous["payload_json"]
            source_updated_at = source_updated_at or previous["source_updated_at"]
        else:
            payload_json = json.dumps(payload, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO layer_snapshots(layer,fetched_at,source_updated_at,payload_json,ok,error)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(layer) DO UPDATE SET fetched_at=excluded.fetched_at,
            source_updated_at=excluded.source_updated_at,payload_json=excluded.payload_json,
            ok=excluded.ok,error=excluded.error
            """,
            (layer, now_iso(), source_updated_at, payload_json, int(ok), error),
        )


def get_snapshot(layer: str):
    with connection() as conn:
        return conn.execute(
            "SELECT * FROM layer_snapshots WHERE layer=?", (layer,)
        ).fetchone()


def get_reports() -> list[dict]:
    now = now_iso()
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM reports WHERE expires_at>? AND status='visivel' ORDER BY created_at DESC",
            (now,),
        ).fetchall()
    return [dict(row) for row in rows]


def insert_report(data: dict) -> None:
    with connection() as conn:
        conn.execute(
            """INSERT INTO reports
            (id,category,description,lat,lon,created_at,expires_at,confirmations,status,source)
            VALUES(:id,:category,:description,:lat,:lon,:created_at,:expires_at,:confirmations,:status,:source)""",
            data,
        )


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rad = math.radians
    dlat, dlon = rad(lat2 - lat1), rad(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))


def find_nearby_report(lat: float, lon: float, category: str, radius_m: float, hours: float):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with connection() as conn:
        rows = conn.execute(
            """SELECT * FROM reports WHERE category=? AND created_at>? AND expires_at>?
            AND status IN ('visivel','pendente')""",
            (category, since, now_iso()),
        ).fetchall()
    best = None
    best_distance = radius_m
    for row in rows:
        distance = distance_m(lat, lon, row["lat"], row["lon"])
        if distance <= best_distance:
            best, best_distance = dict(row), distance
    return best


def corroborate_report(report_id: str, promote_at: int = 2):
    with connection() as conn:
        row = conn.execute(
            "SELECT confirmations,status FROM reports WHERE id=? AND expires_at>?",
            (report_id, now_iso()),
        ).fetchone()
        if not row:
            return None
        confirmations = row["confirmations"] + 1
        status = row["status"]
        if status == "pendente" and confirmations >= promote_at:
            status = "visivel"
        conn.execute(
            "UPDATE reports SET confirmations=?,status=? WHERE id=?",
            (confirmations, status, report_id),
        )
        return {"confirmations": confirmations, "status": status}


def confirm_report(report_id: str) -> int | None:
    with connection() as conn:
        row = conn.execute(
            "SELECT confirmations FROM reports WHERE id=? AND expires_at>? AND status='visivel'",
            (report_id, now_iso()),
        ).fetchone()
        if not row:
            return None
        value = row["confirmations"] + 1
        conn.execute("UPDATE reports SET confirmations=? WHERE id=?", (value, report_id))
        return value


def create_user(user_id: str, email: str, pass_hash: str, salt: str) -> bool:
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO users(id,email,pass_hash,salt,created_at) VALUES(?,?,?,?,?)",
                (user_id, email, pass_hash, salt, now_iso()),
            )
        return True
    except (sqlite3.IntegrityError, psycopg.IntegrityError):
        return False


def get_user_by_email(email: str):
    with connection() as conn:
        return conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()


def create_session(token: str, user_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)",
            (token, user_id, now_iso()),
        )


def get_session(token: str):
    with connection() as conn:
        return conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()


def get_user_by_token(token: str):
    with connection() as conn:
        return conn.execute(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=?",
            (token,),
        ).fetchone()


def save_user_contacts(user_id: str, contacts_json: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE users SET contacts_json=? WHERE id=?", (contacts_json, user_id)
        )


def _flood_key(name: str, lat: float, lon: float) -> str:
    from .collectors.geocoding import normaliza

    normalized = normaliza(name) if name else ""
    return f"{normalized}|{round(lat, 4):.4f}|{round(lon, 4):.4f}"


def record_flood_points(points: list[dict], seen_at: str) -> None:
    cutoff = (datetime.fromisoformat(seen_at) - timedelta(minutes=30)).isoformat()
    with connection() as conn:
        for point in points:
            geometry = point.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []
            if len(coordinates) != 2:
                continue
            lon, lat = coordinates
            properties = point.get("properties") or {}
            name = properties.get("via") or properties.get("referencia") or ""
            key = _flood_key(name, lat, lon)
            existing = conn.execute(
                "SELECT 1 FROM flood_history WHERE key=? AND seen_at>? LIMIT 1",
                (key, cutoff),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO flood_history(key,name,lat,lon,seen_at) VALUES(?,?,?,?,?)",
                (key, name, round(lat, 4), round(lon, 4), seen_at),
            )


def flood_recurrence(days: int = 30) -> list[dict]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connection() as conn:
        rows = conn.execute(
            "SELECT key,name,lat,lon,seen_at FROM flood_history WHERE seen_at>? ORDER BY key,seen_at",
            (since,),
        ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["key"], []).append(dict(row))
    result = []
    for key, items in grouped.items():
        episodes = 1
        for previous, current in pairwise(items):
            gap_hours = (
                datetime.fromisoformat(current["seen_at"]) - datetime.fromisoformat(previous["seen_at"])
            ).total_seconds() / 3600
            if gap_hours > 2:
                episodes += 1
        last = items[-1]
        result.append({
            "key": key, "name": last["name"], "lat": last["lat"], "lon": last["lon"],
            "episodes": episodes, "last_seen": last["seen_at"],
        })
    return result


def purge_flood_history(days: int = 90) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connection() as conn:
        before = conn.execute(
            "SELECT COUNT(*) AS n FROM flood_history WHERE seen_at<?", (cutoff,)
        ).fetchone()["n"]
        conn.execute("DELETE FROM flood_history WHERE seen_at<?", (cutoff,))
    return before
