import json

import httpx
from shapely.geometry import LineString, shape

from .db import distance_m, get_snapshot

OSRM = "https://router.project-osrm.org/route/v1/driving"
WEIGHTS = {"crime": 40, "alagamento": 20, "cemaden": 15, "reports": 15, "inmet": 10}
NEAR_M = {"alagamento": 300.0, "reports": 300.0, "cemaden": 1000.0}
CRIME_PER_KM_FULL = 30.0


def fetch_routes(origin: tuple[float, float], dest: tuple[float, float]) -> list[dict]:
    url = f"{OSRM}/{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
    params = {"geometries": "geojson", "overview": "full", "alternatives": "true"}
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    routes = response.json().get("routes", [])
    return [
        {
            "distance_m": route["distance"],
            "duration_s": route["duration"],
            "coords": route["geometry"]["coordinates"],
        }
        for route in routes
    ]


def _features(layer: str) -> list[dict]:
    snapshot = get_snapshot(layer)
    if not snapshot:
        return []
    return json.loads(snapshot["payload_json"]).get("features", [])


def _layer_points(layer: str) -> list[dict]:
    points = []
    for feature in _features(layer):
        if feature.get("geometry", {}).get("type") == "Point":
            coords = feature["geometry"]["coordinates"]
            points.append({"lat": coords[1], "lon": coords[0], "props": feature.get("properties", {})})
    return points


def _crime_load(line: LineString) -> float:
    total = 0.0
    for feature in _features("crime"):
        geometry = feature.get("geometry", {})
        if geometry.get("type") == "Polygon":
            polygon = shape(geometry)
            if polygon.intersects(line):
                total += float(feature.get("properties", {}).get("total") or 0)
    return total


def _count_near(points: list[dict], coords: list, radius_m: float, security_weight: float = 1.0) -> float:
    total = 0.0
    for point in points:
        nearest = min(
            distance_m(point["lat"], point["lon"], coord[1], coord[0]) for coord in coords
        )
        if nearest <= radius_m:
            weight = security_weight if point["props"].get("category") == "seguranca" else 1.0
            total += weight
    return total


def score_route(coords: list, distance_m_total: float) -> dict:
    line = LineString(coords)
    km = max(distance_m_total / 1000.0, 0.4)
    crime_total = _crime_load(line)
    alagamento = _count_near(_layer_points("alagamento"), coords, NEAR_M["alagamento"])
    cemaden = _count_near(_layer_points("cemaden"), coords, NEAR_M["cemaden"])
    reports = _count_near(
        _layer_points("reports"), coords, NEAR_M["reports"], security_weight=2.0
    )
    inmet_active = 1.0 if _features("inmet") else 0.0
    breakdown = {
        "crime": round(WEIGHTS["crime"] * min(1.0, (crime_total / km) / CRIME_PER_KM_FULL)),
        "alagamento": round(WEIGHTS["alagamento"] * min(1.0, alagamento / 3)),
        "cemaden": round(WEIGHTS["cemaden"] * min(1.0, cemaden / 2)),
        "reports": round(WEIGHTS["reports"] * min(1.0, reports / 3)),
        "inmet": round(WEIGHTS["inmet"] * inmet_active),
    }
    score = min(100, sum(breakdown.values()))
    level = "baixo" if score < 20 else "moderado" if score < 45 else "alto" if score < 70 else "crítico"
    return {
        "score": score,
        "level": level,
        "breakdown": breakdown,
        "crime_cells_total": int(crime_total),
    }
