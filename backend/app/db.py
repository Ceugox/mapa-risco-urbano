import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import settings


def _path() -> Path:
    path = Path(settings.database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection():
    conn = sqlite3.connect(_path())
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
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
            """
        )
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(reports)")]
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
