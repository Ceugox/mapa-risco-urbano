import httpx

URL = "https://painelalertas.cemaden.gov.br/wsAlertas2"


def transform(payload: dict) -> dict:
    features = []
    for alert in payload.get("alertas", []):
        if alert.get("uf") != "SP" or not alert.get("latitude") or not alert.get("longitude"):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(alert["longitude"]), float(alert["latitude"])]},
            "properties": {
                "municipio": alert.get("municipio"), "evento": alert.get("evento"),
                "nivel": alert.get("nivel"), "inicio": alert.get("datahoracriacao"),
            },
        })
    return {"type": "FeatureCollection", "features": features, "source_updated_at": payload.get("atualizado")}


def collect() -> dict:
    with httpx.Client(timeout=30) as client:
        response = client.get(URL, headers={"Accept": "application/json"})
        response.raise_for_status()
        return transform(response.json())
