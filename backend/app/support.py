import time

import httpx

from .db import distance_m

WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE_TTL_S = 86400.0

SUPPORT_LAYERS = [
    ("delegacia_policia_civil", "nm_delegacia_policia_civil", "Delegacia", True),
    ("equipamento_policia_militar", "nm_equipamento", "Polícia Militar", True),
    ("equipamento_guarda_civil_metropolitana", "nm_equipamento", "GCM", True),
    ("equipamento_saude_urgencia_emergencia", "nm_equipamento", "UPA / Emergência", True),
    ("centro_referencia_assistencia_social", "nm_cras", "CRAS", False),
    ("equipamento_saude_ubs_posto_centro", "nm_equipamento", "UBS", False),
    ("equipamento_conselho_tutelar", "nm_equipamento", "Conselho Tutelar", False),
]

_cache: dict[str, tuple[float, list[dict]]] = {}


def _layer_features(layer: str, name_field: str) -> list[dict]:
    cached = _cache.get(layer)
    if cached and time.time() - cached[0] < CACHE_TTL_S:
        return cached[1]
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": f"geoportal:{layer}", "outputFormat": "application/json",
        "srsName": "EPSG:4326", "count": 2000,
    }
    try:
        with httpx.Client(timeout=60) as client:
            features = client.get(WFS, params=params).json().get("features", [])
    except (httpx.HTTPError, ValueError):
        return _cache.get(layer, (0, []))[1]
    points = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        name = feature.get("properties", {}).get(name_field)
        if not name or geometry.get("type") not in ("Point", "MultiPoint"):
            continue
        coords = geometry["coordinates"]
        if geometry["type"] == "MultiPoint":
            coords = coords[0] if coords else []
        if len(coords) >= 2:
            points.append({"nome": name, "lat": coords[1], "lon": coords[0]})
    _cache[layer] = (time.time(), points)
    return points


def _kind(name: str, base: str) -> str:
    upper = name.upper()
    if base == "Delegacia" and ("DDM" in upper or "MULHER" in upper):
        return "Delegacia da Mulher (DDM)"
    if base == "Delegacia" and "DHPP" in upper:
        return "Delegacia (DHPP)"
    return base


def _overpass_open(lat: float, lon: float) -> list[dict]:
    query = (
        "[out:json][timeout:8];node[amenity~'pharmacy|fast_food|convenience']"
        f"[opening_hours](around:800,{lat},{lon});out 8;"
    )
    try:
        response = httpx.post(OVERPASS, data={"data": query}, timeout=12)
        elements = response.json().get("elements", [])
    except (httpx.HTTPError, ValueError):
        return []
    points = []
    for element in elements:
        tags = element.get("tags", {})
        hours = tags.get("opening_hours", "")
        points.append({
            "nome": tags.get("name", "Estabelecimento"),
            "lat": element["lat"], "lon": element["lon"],
            "tipo": "Comércio", "aberto_24h": "24/7" in hours,
            "horario": hours,
        })
    return points


def nearby(lat: float, lon: float, limit: int = 12) -> list[dict]:
    results = []
    for layer, name_field, base, always_open in SUPPORT_LAYERS:
        for point in _layer_features(layer, name_field):
            results.append({
                "nome": point["nome"], "lat": point["lat"], "lon": point["lon"],
                "tipo": _kind(point["nome"], base), "aberto_24h": always_open,
                "horario": "24 horas" if always_open else "horário comercial",
                "distancia_m": round(distance_m(lat, lon, point["lat"], point["lon"])),
            })
    for point in _overpass_open(lat, lon):
        point["distancia_m"] = round(distance_m(lat, lon, point["lat"], point["lon"]))
        results.append(point)
    results.sort(key=lambda item: item["distancia_m"])
    return results[:limit]
