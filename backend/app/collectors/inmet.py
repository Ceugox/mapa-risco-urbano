import re

import httpx

URL = "https://apiprevmet3.inmet.gov.br/avisos/ativos"


def _polygon(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = re.search(r"POLYGON\s*\(\((.*?)\)\)", text, re.IGNORECASE)
    if not match:
        return None
    coords = []
    for pair in match.group(1).split(","):
        values = pair.strip().split()
        if len(values) >= 2:
            coords.append([float(values[0]), float(values[1])])
    return {"type": "Polygon", "coordinates": [coords]} if len(coords) >= 3 else None


def collect() -> dict:
    with httpx.Client(timeout=45) as client:
        response = client.get(URL)
        response.raise_for_status()
        payload = response.json()
    features = []
    for aviso in payload.get("hoje", []) + payload.get("futuro", []):
        states = aviso.get("estados") or []
        states_text = str(states).upper()
        municipalities = str(aviso.get("municipios") or "").upper()
        if "SP" not in states_text and "SÃO PAULO" not in states_text and "SAO PAULO" not in municipalities:
            continue
        geometry = _polygon(aviso.get("poligono")) or aviso.get("geometry")
        if not geometry:
            continue
        features.append({
            "type": "Feature", "geometry": geometry,
            "properties": {key: aviso.get(key) for key in (
                "severidade", "aviso_cor", "descricao", "inicio", "fim", "instrucoes"
            )},
        })
    return {"type": "FeatureCollection", "features": features}
