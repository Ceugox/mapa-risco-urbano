import re

import httpx
from bs4 import BeautifulSoup

from .geocoding import cached_resolve

URL = "https://www.cgesp.org/v3/alagamentos.jsp"
STATUS = {
    "ativo-intransitavel": ("ativo", 4), "ativo-transitavel": ("ativo", 2),
    "inativo-intransitavel": ("inativo", 1), "inativo-transitavel": ("inativo", 1),
}


def parse_pontos(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    points, zone = [], None
    for node in soup.select("h1.tit-bairros, table.tb-pontos-de-alagamentos"):
        if node.name == "h1":
            zone = node.get_text(strip=True)
            continue
        cell = node.select_one("td.bairro")
        bairro = cell.get_text(strip=True) if cell else None
        for div in node.select("div.ponto-de-alagamento"):
            marker = div.select_one("li[title]")
            classes = marker.get("class", []) if marker else []
            status, severity = next((STATUS[c] for c in classes if c in STATUS), ("desconhecido", 0))
            local = div.select_one("li.col-local")
            detail = div.select_one("li.arial-descr-alag:not(.col-local)")
            local_text = local.get_text("\n", strip=True) if local else ""
            detail_text = detail.get_text("\n", strip=True) if detail else ""
            schedule = re.search(r"De\s+(\d{2}:\d{2})\s*a\s*(\d{2}:\d{2})?", local_text)
            points.append({
                "zona": zone, "bairro": bairro,
                "via": local_text.split("\n")[-1].strip() if local_text else None,
                "sentido": (m := re.search(r"Sentido:\s*(.+)", detail_text)) and m.group(1).strip(),
                "referencia": (m := re.search(r"Refer[êe]ncia:\s*(.+)", detail_text)) and m.group(1).strip(),
                "inicio": schedule.group(1) if schedule else None,
                "fim": schedule.group(2) if schedule else None, "status": status,
                "transitabilidade": marker.get("title") if marker else None,
                "severidade": severity,
            })
    return points


def collect() -> dict:
    with httpx.Client(timeout=30, headers={"User-Agent": "MapaRiscoUrbano/0.1"}) as client:
        response = client.get(URL)
        response.raise_for_status()
        points = parse_pontos(response.text)
    features, not_found = [], 0
    for point in points:
        location = cached_resolve(point["via"], point["referencia"])
        if "lat" not in location:
            not_found += 1
            continue
        properties = {key: point.get(key) for key in (
            "via", "referencia", "sentido", "status", "transitabilidade", "severidade", "inicio"
        )}
        properties["precision"] = location["precision"]
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [location["lon"], location["lat"]]}, "properties": properties})
    return {"type": "FeatureCollection", "features": features, "nao_localizados": not_found}
