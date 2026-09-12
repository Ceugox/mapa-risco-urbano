import json

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..db import distance_m, get_snapshot
from ..ingest import ingest_text

router = APIRouter(prefix="/api/webhooks/whatsapp")

NEARBY_M = 1500.0
LAYERS = ("alagamento", "cemaden", "reports")


def _nearby_summary(lat: float, lon: float) -> str:
    lines = []
    for layer in LAYERS:
        snapshot = get_snapshot(layer)
        if not snapshot or not snapshot["ok"]:
            continue
        features = json.loads(snapshot["payload_json"]).get("features", [])
        near = []
        for feature in features:
            coords = feature.get("geometry", {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            distance = distance_m(lat, lon, coords[1], coords[0])
            if distance <= NEARBY_M:
                near.append((distance, feature.get("properties", {})))
        near.sort(key=lambda item: item[0])
        if near:
            label = {"alagamento": "Alagamento", "cemaden": "Alerta CEMADEN", "reports": "Relato"}[layer]
            top = near[0]
            detail = top[1].get("descricao") or top[1].get("description") or top[1].get("municipio") or ""
            lines.append(f"• {label} a {int(top[0])} m: {detail[:80]}")
    if not lines:
        return "Nenhum risco ativo num raio de 1,5 km desse ponto."
    return "Riscos ativos perto de você:\n" + "\n".join(lines[:5])


def _send_reply(to: str, body: str) -> bool:
    if not (settings.whatsapp_token and settings.whatsapp_phone_id and to):
        return False
    url = f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_id}/messages"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body}},
            timeout=15,
        )
        return response.status_code < 300
    except httpx.HTTPError:
        return False


def _handle_message(message: dict) -> dict:
    mtype = message.get("type")
    if mtype == "text":
        return ingest_text(message.get("text", {}).get("body", ""), channel="whatsapp")
    if mtype == "location":
        location = message.get("location", {})
        lat, lon = location.get("latitude"), location.get("longitude")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            return {"ingested": False, "reason": "localização inválida"}
        summary = _nearby_summary(lat, lon)
        replied = _send_reply(message.get("from", ""), summary)
        return {"ingested": True, "action": "risk_lookup", "replied": replied, "summary": summary}
    return {"ingested": False, "reason": f"tipo não suportado: {mtype}"}


@router.get("")
def verify(request: Request):
    params = request.query_params
    ok = (
        settings.whatsapp_verify_token
        and params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    )
    if not ok:
        raise HTTPException(403, "verificação falhou")
    return PlainTextResponse(params.get("hub.challenge", ""))


@router.post("")
def inbound(payload: dict):
    results = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            messages = change.get("value", {}).get("messages", [])
            for message in messages[:5]:
                results.append(_handle_message(message))
    return {"processed": len(results), "results": results}
