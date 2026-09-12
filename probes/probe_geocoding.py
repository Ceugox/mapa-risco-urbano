"""Testa o elo fraco da camada de alagamento: o CGE entrega texto, nao coordenada.

Sem geocodificacao nao ha pino no mapa. Este script mede a taxa de acerto do
Nominatim (OpenStreetMap) sobre os pontos reais coletados do CGE, usando
"via + referencia" como cruzamento de ruas.
"""

import json
import sys
import time
from datetime import datetime, timezone

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "MapaRiscoUrbano/0.1 (projeto civico; contato@exemplo.org)"}

# caixa delimitadora do municipio de Sao Paulo
BBOX = (-46.83, -24.01, -46.36, -23.35)


def dentro_da_cidade(lat: float, lon: float) -> bool:
    return BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]


def geocodifica(consulta: str) -> dict | None:
    resp = requests.get(
        NOMINATIM,
        params={
            "q": consulta,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "br",
            "viewbox": ",".join(map(str, BBOX)),
            "bounded": 1,
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    dados = resp.json()
    if not dados:
        return None
    hit = dados[0]
    return {"lat": float(hit["lat"]), "lon": float(hit["lon"]), "match": hit.get("display_name")}


def main() -> int:
    with open("saida_cge.json", encoding="utf-8") as fh:
        pontos = json.load(fh)["pontos"]

    resultados = []
    for ponto in pontos:
        via, ref = ponto.get("via"), ponto.get("referencia")
        if not via:
            continue

        tentativas = [f"{via} e {ref}, São Paulo, SP" if ref else None, f"{via}, São Paulo, SP"]
        achado, usada = None, None
        for consulta in [t for t in tentativas if t]:
            achado = geocodifica(consulta)
            time.sleep(1.1)  # politica de uso do Nominatim: 1 req/s
            if achado and dentro_da_cidade(achado["lat"], achado["lon"]):
                usada = consulta
                break
            achado = None

        resultados.append(
            {
                "via": via,
                "referencia": ref,
                "consulta_que_funcionou": usada,
                "coordenada": achado,
            }
        )

    com_coord = [r for r in resultados if r["coordenada"]]
    por_cruzamento = [r for r in com_coord if r["consulta_que_funcionou"] and " e " in r["consulta_que_funcionou"]]

    relatorio = {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "geocodificador": "Nominatim/OSM",
        "pontos_testados": len(resultados),
        "geocodificados": len(com_coord),
        "taxa_acerto_pct": round(100 * len(com_coord) / len(resultados), 1) if resultados else 0,
        "acerto_no_cruzamento_de_ruas": len(por_cruzamento),
        "acerto_apenas_na_via": len(com_coord) - len(por_cruzamento),
        "falhas": [r["via"] for r in resultados if not r["coordenada"]],
        "amostra": com_coord[:3],
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    with open("saida_geocoding.json", "w", encoding="utf-8") as fh:
        json.dump({"relatorio": relatorio, "resultados": resultados}, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
