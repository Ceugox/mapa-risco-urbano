"""Prova de conceito: CEMADEN (alertas de desastre).

O CEMADEN nao publica API REST documentada. Este script sonda os endpoints dos
paineis publicos e valida o unico que devolve JSON estruturado: `wsAlertas2`,
que alimenta o Painel de Alertas com os alertas vigentes (municipio, codigo
IBGE, nivel, coordenadas).

Endpoint nao documentado = sem contrato de estabilidade. Tratar como scraping:
cache do ultimo estado valido + alerta de falha.
"""

import collections
import json
import sys
import time
from datetime import datetime, timezone

import requests

URL_ALERTAS = "https://painelalertas.cemaden.gov.br/wsAlertas2"

HEADERS = {
    "User-Agent": "MapaRiscoUrbano/0.1 (projeto civico)",
    "Accept": "application/json, text/plain, */*",
}

CANDIDATOS = [
    ("painel_alertas_html", "https://painelalertas.cemaden.gov.br/"),
    ("painel_alertas_api", "https://painelalertas.cemaden.gov.br/api/alertas"),
    ("alertas_vigentes", "http://www2.cemaden.gov.br/alertas-vigentes/"),
    ("pluviometros_sp", "http://sjc.salvar.cemaden.gov.br/resources/graficos/interativo/getJson2.php?uf=SP"),
    ("mapa_interativo", "https://mapainterativo.cemaden.gov.br/"),
]


def sonda(nome: str, url: str) -> dict:
    started = time.monotonic()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException as exc:
        return {"nome": nome, "url": url, "ok": False, "erro": f"{type(exc).__name__}"}

    out = {
        "nome": nome,
        "url": url,
        "status": resp.status_code,
        "latencia_s": round(time.monotonic() - started, 2),
        "bytes": len(resp.content),
        "content_type": resp.headers.get("content-type", "").split(";")[0],
    }
    try:
        payload = resp.json()
        out["json"] = True
        out["formato"] = type(payload).__name__
        out["tamanho"] = len(payload) if hasattr(payload, "__len__") else None
        out["amostra"] = json.dumps(payload, ensure_ascii=False)[:300]
    except ValueError:
        out["json"] = False
        out["precisa_js"] = "app" in resp.text.lower() and "<script" in resp.text.lower()
    return out


def probe_alertas() -> dict:
    started = time.monotonic()
    resp = requests.get(URL_ALERTAS, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    alertas = payload.get("alertas", [])

    sp = [a for a in alertas if a.get("uf") == "SP"]
    com_coord = [a for a in alertas if a.get("latitude") and a.get("longitude")]

    return {
        "endpoint": URL_ALERTAS,
        "latencia_s": round(time.monotonic() - started, 2),
        "bytes": len(resp.content),
        "atualizado_em_declarado": payload.get("atualizado"),
        "alertas_vigentes": len(alertas),
        "alertas_sp": len(sp),
        "com_coordenada": len(com_coord),
        "por_evento": collections.Counter(a.get("evento") for a in alertas).most_common(),
        "campos": sorted(alertas[0].keys()) if alertas else [],
        "amostra_sp": sp[:2],
    }


def main() -> int:
    relatorio = {
        "fonte": "CEMADEN",
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "alertas": probe_alertas(),
        "outras_sondagens": [sonda(n, u) for n, u in CANDIDATOS],
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    with open("saida_cemaden.json", "w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
