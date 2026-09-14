import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ..config import settings
from ..ingest import ingest_text
from ..risk import summarize

router = APIRouter(prefix="/api/webhooks/whatsapp")


def _nearby_summary(lat: float, lon: float) -> str:
    result = summarize(lat, lon)
    lines = [f"• {item['label']}" for item in result["items"]]
    if not lines:
        return "Nenhum risco ativo num raio de 800 m desse ponto."
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
