"""Prova de conceito: camada de crime (SSP-SP) e base historica (GeoSampa).

Crime nao e tempo real. O objetivo aqui e medir o que da para automatizar:
existe download programatico? qual a defasagem? qual a granularidade espacial?

GeoSampa expoe WFS/WMS - serve para a camada de "rua que alaga sempre" e para
os limites de distrito/subprefeitura usados na agregacao.
"""

import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

HEADERS = {"User-Agent": "MapaRiscoUrbano/0.1 (projeto civico)"}

CKAN = "https://dados.gov.br/api/3/action/package_search"
GEOSAMPA_WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"


def timed_get(url: str, params: dict | None = None, timeout: int = 45) -> dict:
    started = time.monotonic()
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return {"ok": False, "erro": f"{type(exc).__name__}: {str(exc)[:120]}"}
    return {
        "ok": resp.ok,
        "status": resp.status_code,
        "latencia_s": round(time.monotonic() - started, 2),
        "bytes": len(resp.content),
        "content_type": resp.headers.get("content-type", "").split(";")[0],
        "_resp": resp,
    }


def probe_ssp_portal() -> list[dict]:
    """O portal de transparencia da SSP e ASP.NET com postback; mede se ha rota direta."""
    alvos = [
        "https://www.ssp.sp.gov.br/estatistica/consultas",
        "https://www.ssp.sp.gov.br/transparenciassp/Consulta.aspx",
        "https://www.ssp.sp.gov.br/transparenciassp/Apresentacao.aspx",
    ]
    saida = []
    for url in alvos:
        res = timed_get(url)
        res.pop("_resp", None)
        res["url"] = url
        saida.append(res)
    return saida


def probe_ckan_ssp() -> dict:
    """Portal nacional de dados abertos: existem datasets da SSP-SP publicados?"""
    res = timed_get(CKAN, {"q": "seguranca publica sao paulo ocorrencias", "rows": 10})
    resp = res.pop("_resp", None)
    if not resp or not res.get("ok"):
        return res
    try:
        payload = resp.json()
    except ValueError:
        return res | {"erro": "resposta nao-json"}

    resultados = payload.get("result", {}).get("results", [])
    res["total_encontrado"] = payload.get("result", {}).get("count")
    res["datasets"] = [
        {
            "titulo": d.get("title"),
            "org": (d.get("organization") or {}).get("title"),
            "atualizado": d.get("metadata_modified"),
            "formatos": sorted({r.get("format") for r in d.get("resources", []) if r.get("format")}),
        }
        for d in resultados[:6]
    ]
    return res


def probe_geosampa_wfs() -> dict:
    """Lista as camadas WFS publicadas, filtrando as de interesse."""
    res = timed_get(GEOSAMPA_WFS, {"service": "WFS", "request": "GetCapabilities", "version": "2.0.0"})
    resp = res.pop("_resp", None)
    if not resp or not res.get("ok"):
        return res

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        return res | {"erro": f"xml invalido: {exc}"}

    ns = {"wfs": "http://www.opengis.net/wfs/2.0"}
    nomes = [n.text for n in root.findall(".//wfs:FeatureType/wfs:Name", ns) if n.text]
    interesse = [n for n in nomes if any(t in n.lower() for t in ("alag", "inund", "risco", "distrito", "subpref"))]
    res["camadas_total"] = len(nomes)
    res["camadas_de_interesse"] = interesse[:15]
    return res


def main() -> int:
    relatorio = {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "ssp_portal": probe_ssp_portal(),
        "dados_gov_br": probe_ckan_ssp(),
        "geosampa_wfs": probe_geosampa_wfs(),
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2)[:6000])
    with open("saida_crime_geosampa.json", "w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
