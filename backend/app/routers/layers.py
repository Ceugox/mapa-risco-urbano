import json

from fastapi import APIRouter, HTTPException

from ..db import get_snapshot

router = APIRouter(prefix="/api/layers")
LAYERS = ["alagamento", "cemaden", "inmet", "clima", "crime", "reports"]


def _count(payload: dict) -> int:
    return len(payload.get("features", [])) if isinstance(payload, dict) else 0


@router.get("")
def list_layers():
    result = []
    for layer in LAYERS:
        row = get_snapshot(layer)
        result.append({
            "layer": layer, "fetched_at": row["fetched_at"] if row else None,
            "source_updated_at": row["source_updated_at"] if row else None,
            "ok": bool(row and row["ok"]), "error": row["error"] if row else "Aguardando coleta",
            "count": _count(json.loads(row["payload_json"])) if row else 0,
        })
    return result


@router.get("/{layer}")
def get_layer(layer: str):
    if layer not in LAYERS:
        raise HTTPException(404, "Camada não encontrada")
    row = get_snapshot(layer)
    if not row:
        raise HTTPException(404, "Camada ainda não coletada")
    payload = json.loads(row["payload_json"])
    payload["_metadata"] = {
        "layer": layer, "fetched_at": row["fetched_at"],
        "source_updated_at": row["source_updated_at"], "ok": bool(row["ok"]), "error": row["error"],
    }
    return payload
