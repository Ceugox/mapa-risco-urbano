import traceback
from collections.abc import Callable

from ..db import store_snapshot


def run_collector(name: str, fn: Callable[[], dict]) -> dict:
    try:
        payload = fn()
        store_snapshot(name, payload, ok=True, source_updated_at=payload.get("source_updated_at"))
        return payload
    except Exception as exc:  # noqa: BLE001
        store_snapshot(name, {}, ok=False, error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        return {}
