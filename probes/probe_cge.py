"""Prova de conceito: coleta de pontos de alagamento do CGE-SP.

Nao ha API publica documentada; a pagina e HTML server-side, sem JS, o que
torna o scraping simples e estavel. Este script extrai os pontos em formato
estruturado e reporta metricas de viabilidade (latencia, volume, carimbo).
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL_ALAGAMENTOS = "https://www.cgesp.org/v3/alagamentos.jsp"
URL_HOME = "https://www.cgesp.org/v3/"

HEADERS = {
    "User-Agent": "MapaRiscoUrbano/0.1 (projeto civico; contato@exemplo.org)",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# classe do <li> marcador -> (status, severidade 1..4)
STATUS = {
    "ativo-intransitavel": ("ativo", 4),
    "ativo-transitavel": ("ativo", 2),
    "inativo-intransitavel": ("inativo", 1),
    "inativo-transitavel": ("inativo", 1),
}


def fetch(url: str) -> tuple[str, float, int]:
    started = time.monotonic()
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text, round(time.monotonic() - started, 2), len(resp.content)


def parse_pontos(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    pontos: list[dict] = []
    zona_atual = None

    for node in soup.select("h1.tit-bairros, table.tb-pontos-de-alagamentos"):
        if node.name == "h1":
            zona_atual = node.get_text(strip=True)
            continue

        bairro_cell = node.select_one("td.bairro")
        bairro = bairro_cell.get_text(strip=True) if bairro_cell else None

        for div in node.select("div.ponto-de-alagamento"):
            marker = div.select_one("li[title]")
            classes = marker.get("class", []) if marker else []
            status, severidade = next(
                (STATUS[c] for c in classes if c in STATUS), ("desconhecido", 0)
            )

            local = div.select_one("li.col-local")
            detalhe = div.select_one("li.arial-descr-alag:not(.col-local)")
            local_txt = local.get_text("\n", strip=True) if local else ""
            det_txt = detalhe.get_text("\n", strip=True) if detalhe else ""

            horario = re.search(r"De\s+(\d{2}:\d{2})\s*a\s*(\d{2}:\d{2})?", local_txt)
            via = local_txt.split("\n")[-1].strip() if local_txt else None
            sentido = re.search(r"Sentido:\s*(.+)", det_txt)
            referencia = re.search(r"Refer[êe]ncia:\s*(.+)", det_txt)

            pontos.append(
                {
                    "zona": zona_atual,
                    "bairro": bairro,
                    "via": via,
                    "sentido": sentido.group(1).strip() if sentido else None,
                    "referencia": referencia.group(1).strip() if referencia else None,
                    "inicio": horario.group(1) if horario else None,
                    "fim": horario.group(2) if horario else None,
                    "status": status,
                    "transitabilidade": marker.get("title") if marker else None,
                    "severidade": severidade,
                }
            )

    return pontos


def parse_home(html: str) -> dict:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    banner = re.search(r"Pontos de Alagamento:\s*(\d+)\s*ativos", text, re.I)
    stamp = re.search(r"(\d{2}/\d{2}/\d{4}[^\d]{0,12}\d{2}:\d{2})", text)
    return {
        "banner_ativos": int(banner.group(1)) if banner else None,
        "carimbo_pagina": stamp.group(1) if stamp else None,
    }


def main() -> int:
    html, latencia, tamanho = fetch(URL_ALAGAMENTOS)
    pontos = parse_pontos(html)
    home_html, _, _ = fetch(URL_HOME)
    home = parse_home(home_html)

    ativos = [p for p in pontos if p["status"] == "ativo"]
    intransitaveis = [p for p in ativos if p["severidade"] == 4]
    geocodificaveis = [p for p in pontos if p["via"] and p["referencia"]]

    relatorio = {
        "fonte": "CGE-SP",
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "http": {"latencia_s": latencia, "bytes": tamanho, "javascript_necessario": False},
        "volume": {
            "pontos_total": len(pontos),
            "ativos": len(ativos),
            "ativos_intransitaveis": len(intransitaveis),
            "com_via_e_referencia": len(geocodificaveis),
        },
        "consistencia_com_banner_home": home,
        "amostra": pontos[:3],
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))

    with open("saida_cge.json", "w", encoding="utf-8") as fh:
        json.dump({"relatorio": relatorio, "pontos": pontos}, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
