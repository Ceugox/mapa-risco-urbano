import json

from fastapi import APIRouter, HTTPException

from ..db import flood_recurrence, get_snapshot

router = APIRouter(prefix="/api/layers")
LAYERS = ["alagamento", "cemaden", "inmet", "clima", "crime", "reports", "alagamento_hist"]
FLOOD_HIST_DAYS = 30


def _count(payload: dict) -> int:
    return len(payload.get("features", [])) if isinstance(payload, dict) else 0


def _flood_hist_payload() -> dict:
    points = flood_recurrence(FLOOD_HIST_DAYS)
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [point["lon"], point["lat"]]},
        "properties": {
            "name": point["name"], "episodes": point["episodes"],
            "last_seen": point["last_seen"], "days": FLOOD_HIST_DAYS,
        },
    } for point in points]
    return {"type": "FeatureCollection", "features": features}


@router.get("")
def list_layers():
    result = []
    for layer in LAYERS:
        if layer == "alagamento_hist":
            # Camada derivada: sua idade é a da última coleta do CGE, não "agora".
            source = get_snapshot("alagamento")
            result.append({
                "layer": layer, "fetched_at": source["fetched_at"] if source else None,
                "source_updated_at": None, "ok": bool(source and source["ok"]),
                "error": source["error"] if source else "Aguardando coleta",
                "count": _count(_flood_hist_payload()),
            })
            continue
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
    if layer == "alagamento_hist":
        payload = _flood_hist_payload()
        source = get_snapshot("alagamento")
        payload["_metadata"] = {
            "layer": layer, "fetched_at": source["fetched_at"] if source else None,
            "source_updated_at": None, "ok": bool(source and source["ok"]),
            "error": source["error"] if source else None,
        }
        return payload
    row = get_snapshot(layer)
    if not row:
        raise HTTPException(404, "Camada ainda não coletada")
    payload = json.loads(row["payload_json"])
    payload["_metadata"] = {
        "layer": layer, "fetched_at": row["fetched_at"],
        "source_updated_at": row["source_updated_at"], "ok": bool(row["ok"]), "error": row["error"],
    }
    return payload
