"""Prova de conceito: camada de clima severo.

Testa tres caminhos:
  1. Open-Meteo   - previsao/observacao horaria, sem chave, uso livre
  2. INMET        - avisos meteorologicos e estacoes automaticas (API publica)
  3. INMET alertas- endpoint de avisos vigentes

Mede disponibilidade, latencia, frescura do dado e se ha georreferencia.
"""

import json
import sys
import time
from datetime import datetime, timezone

import requests

SP = {"lat": -23.5505, "lon": -46.6333}
HEADERS = {"User-Agent": "MapaRiscoUrbano/0.1 (projeto civico)"}


def timed_get(url: str, params: dict | None = None, timeout: int = 30) -> dict:
    started = time.monotonic()
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        return {"ok": False, "erro": f"{type(exc).__name__}: {exc}"}
    out = {
        "ok": resp.ok,
        "status": resp.status_code,
        "latencia_s": round(time.monotonic() - started, 2),
        "bytes": len(resp.content),
        "url_final": resp.url,
    }
    try:
        out["json"] = resp.json()
    except ValueError:
        out["texto"] = resp.text[:400]
    return out


def probe_open_meteo() -> dict:
    res = timed_get(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": SP["lat"],
            "longitude": SP["lon"],
            "current": "temperature_2m,precipitation,rain,wind_gusts_10m,weather_code",
            "hourly": "precipitation_probability,precipitation",
            "forecast_days": 1,
            "timezone": "America/Sao_Paulo",
        },
    )
    payload = res.pop("json", {})
    res["amostra_atual"] = payload.get("current")
    res["intervalo_horario"] = payload.get("hourly", {}).get("time", [])[:3]
    res["chave_necessaria"] = False
    return res


def probe_inmet_estacoes() -> dict:
    """Estacoes automaticas: catalogo com lat/lon de todas as estacoes."""
    res = timed_get("https://apitempo.inmet.gov.br/estacoes/T")
    payload = res.pop("json", None)
    if isinstance(payload, list):
        sp = [e for e in payload if e.get("SG_ESTADO") == "SP"]
        res["estacoes_total"] = len(payload)
        res["estacoes_sp"] = len(sp)
        res["amostra"] = sp[:2]
    return res


def probe_inmet_dados_hoje() -> dict:
    """Leituras horarias de uma estacao (A701 = Sao Paulo / Mirante de Santana)."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    res = timed_get(f"https://apitempo.inmet.gov.br/estacao/{hoje}/{hoje}/A701")
    payload = res.pop("json", None)
    if isinstance(payload, list) and payload:
        ultima = payload[-1]
        res["leituras_hoje"] = len(payload)
        res["ultima_leitura"] = {
            k: ultima.get(k)
            for k in ("DT_MEDICAO", "HR_MEDICAO", "CHUVA", "TEM_INS", "VEN_RAJ", "UMD_INS")
        }
    return res


def probe_inmet_avisos() -> dict:
    """Avisos meteorologicos vigentes (chuva intensa, vendaval, etc)."""
    res = timed_get("https://apiprevmet3.inmet.gov.br/avisos/ativos")
    payload = res.pop("json", None)
    if isinstance(payload, dict):
        hoje = payload.get("hoje", [])
        futuro = payload.get("futuro", [])
        res["avisos_hoje"] = len(hoje)
        res["avisos_futuro"] = len(futuro)
        if hoje:
            a = hoje[0]
            res["amostra_campos"] = sorted(a.keys())
            res["amostra"] = {
                k: a.get(k)
                for k in ("descricao", "severidade", "inicio", "fim", "aviso_cor")
                if k in a
            }
            res["tem_poligono"] = any(
                k in a for k in ("poligono", "geometry", "geocodes", "municipios")
            )
    return res


def main() -> int:
    relatorio = {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "open_meteo": probe_open_meteo(),
        "inmet_estacoes": probe_inmet_estacoes(),
        "inmet_leituras": probe_inmet_dados_hoje(),
        "inmet_avisos": probe_inmet_avisos(),
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2)[:6000])
    with open("saida_clima.json", "w", encoding="utf-8") as fh:
        json.dump(relatorio, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
