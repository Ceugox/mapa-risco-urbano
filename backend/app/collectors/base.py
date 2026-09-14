import traceback
from collections.abc import Callable

from ..db import now_iso, record_flood_points, store_snapshot


def run_collector(name: str, fn: Callable[[], dict]) -> dict:
    try:
        payload = fn()
        store_snapshot(name, payload, ok=True, source_updated_at=payload.get("source_updated_at"))
        if name == "alagamento":
            try:
                record_flood_points(payload.get("features", []), now_iso())
            except Exception:  # noqa: BLE001
                traceback.print_exc()
        return payload
    except Exception as exc:  # noqa: BLE001
        store_snapshot(name, {}, ok=False, error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {}
