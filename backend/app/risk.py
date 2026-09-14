import json
from statistics import mean

import h3

from .db import distance_m, get_snapshot, now_iso

H3_RESOLUTION = 8
DEFAULT_RADIUS_M = 800

# Camadas de ponto/polígono: contamos ocorrências dentro do disco H3 e
# guardamos a distância até a mais próxima.
POINT_LAYERS = ("alagamento", "cemaden", "inmet", "clima", "reports")

# Peso de cada ocorrência no score (0-100, mesma escala de app/routing.py).
WEIGHTS = {"alagamento": 8, "cemaden": 12, "inmet": 10, "clima": 5, "reports": 10, "crime": 2}

NOUNS = {
    "alagamento": ("ponto", "pontos", "de alagamento"),
    "cemaden": ("alerta", "alertas", "CEMADEN"),
    "inmet": ("aviso", "avisos", "INMET"),
    "clima": ("leitura", "leituras", "de clima"),
    "reports": ("relato", "relatos", "da comunidade"),
}


def _feature_point(feature: dict) -> tuple[float, float] | None:
    geometry = feature.get("geometry") or {}
    coords = geometry.get("coordinates")
    if not coords:
        return None
    if geometry.get("type") == "Point":
        lon, lat = coords[0], coords[1]
        return lat, lon
    if geometry.get("type") == "Polygon":
        ring = coords[0] if coords else []
        if not ring:
            return None
        lat = sum(point[1] for point in ring) / len(ring)
        lon = sum(point[0] for point in ring) / len(ring)
        return lat, lon
    return None


def _point_layer_item(layer: str, payload: dict, lat: float, lon: float, disk: set) -> dict | None:
    count = 0
    nearest = None
    for feature in payload.get("features", []):
        point = _feature_point(feature)
        if point is None:
            continue
        f_lat, f_lon = point
        if h3.latlng_to_cell(f_lat, f_lon, H3_RESOLUTION) not in disk:
            continue
        count += 1
        distance = distance_m(lat, lon, f_lat, f_lon)
        if nearest is None or distance < nearest:
            nearest = distance
    if count == 0:
        return None
    singular, plural, suffix = NOUNS[layer]
    noun = singular if count == 1 else plural
    label = f"{count} {noun} {suffix}"
    nearest_m = round(nearest) if nearest is not None else None
    if nearest_m is not None:
        label = f"{label} a {nearest_m} m"
    return {"layer": layer, "count": count, "label": label, "nearest_m": nearest_m}


def _crime_item(payload: dict, lat: float, lon: float, disk: set) -> dict | None:
    features = payload.get("features", [])
    if not features:
        return None
    totals = [feature.get("properties", {}).get("total", 0) or 0 for feature in features]
    average = mean(totals) if totals else 0
    matched_total = 0
    nearest = None
    for feature in features:
        properties = feature.get("properties", {})
        cell = properties.get("h3")
        if cell not in disk:
            continue
        # A camada já é agregada por célula: usamos o máximo entre as
        # células vizinhas, não a soma (evita contar a mesma área 2x).
        matched_total = max(matched_total, properties.get("total", 0) or 0)
        center_lat, center_lon = h3.cell_to_latlng(cell)
        distance = distance_m(lat, lon, center_lat, center_lon)
        if nearest is None or distance < nearest:
            nearest = distance
    if matched_total == 0:
        return None
    label = "crime: célula acima da média" if matched_total > average else "crime: célula dentro da média"
    nearest_m = round(nearest) if nearest is not None else None
    return {"layer": "crime", "count": matched_total, "label": label, "nearest_m": nearest_m}


def summarize(lat: float, lon: float, radius_m: float = DEFAULT_RADIUS_M) -> dict:
    """Resume o risco num raio de ~radius_m ao redor de (lat, lon).

    A vizinhança é aproximada por uma célula H3 resolução 8 e seu anel
    (grid_disk k=1), o que cobre algo perto de 800 m de raio a partir do
    ponto. Por isso radius_m hoje documenta o raio alvo, sem alterar o
    tamanho do anel consultado.
    """
    origin = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
    disk = set(h3.grid_disk(origin, 1))

    items = []
    fetched_ats = []
    for layer in POINT_LAYERS:
        row = get_snapshot(layer)
        if not row or not row["ok"]:
            continue
        fetched_ats.append(row["fetched_at"])
        item = _point_layer_item(layer, _payload(row), lat, lon, disk)
        if item:
            items.append(item)

    crime_row = get_snapshot("crime")
    if crime_row and crime_row["ok"]:
        fetched_ats.append(crime_row["fetched_at"])
        item = _crime_item(_payload(crime_row), lat, lon, disk)
        if item:
            items.append(item)

    score = min(100, sum(WEIGHTS[item["layer"]] * item["count"] for item in items))
    level = "baixo" if score < 20 else "moderado" if score < 45 else "alto"

    updated_at = max(fetched_ats) if fetched_ats else now_iso()
    return {"level": level, "score": score, "items": items, "updated_at": updated_at}


def _payload(row) -> dict:
    return json.loads(row["payload_json"])
