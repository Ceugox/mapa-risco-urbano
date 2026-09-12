import httpx

POINTS = {
    "centro": (-23.55, -46.63), "norte": (-23.47, -46.62),
    "sul": (-23.70, -46.70), "leste": (-23.55, -46.45), "oeste": (-23.55, -46.75),
}


def collect() -> dict:
    features = []
    params = {
        "current": "temperature_2m,precipitation,wind_gusts_10m,weather_code",
        "hourly": "precipitation_probability", "forecast_days": 1,
        "timezone": "America/Sao_Paulo",
    }
    with httpx.Client(timeout=30) as client:
        for name, (lat, lon) in POINTS.items():
            response = client.get(
                "https://api.open-meteo.com/v1/forecast",
                params={**params, "latitude": lat, "longitude": lon},
            )
            response.raise_for_status()
            data = response.json()
            current = data.get("current", {})
            features.append({
                "type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "nome": name, "temperature_2m": current.get("temperature_2m"),
                    "precipitation": current.get("precipitation"),
                    "wind_gusts_10m": current.get("wind_gusts_10m"),
                    "weather_code": current.get("weather_code"),
                    "precipitation_probability": (data.get("hourly", {}).get("precipitation_probability") or [])[:6],
                },
            })
    return {"type": "FeatureCollection", "features": features}
