import json
import re
import unicodedata
from pathlib import Path

import httpx
from shapely.geometry import shape
from shapely.ops import nearest_points, unary_union

from ..db import connection

WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
CAMADA = "geoportal:segmento_logradouro"
TIPOS = r"^(AV|AVENIDA|R|RUA|PCA|PC|PTE|VD|EST|ROD|MARG|MARGINAL|CV|TUN|TRV|AL|LGO|ACS|COMPL)\b\.?\s*"
TITULOS = r"^(CEL|CAP|TEN|SGT|GEN|MAL|BRIG|DR|DRA|PROF|PROFA|PE|SEN|DEP|VER|GOV|PRES|MIN|ENG|JORN|SARG|VIS|CDE|CDSSA|MAJ)\b\.?\s*"
_PROBE_CACHE = {}


def normaliza(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\(.*?\)", " ", texto)
    texto = re.split(r"[-–]", texto)[0]
    texto = re.sub(r"[.,]", " ", texto).strip()
    texto = re.sub(TIPOS, "", texto).strip()
    texto = re.sub(TITULOS, "", texto).strip()
    return re.sub(r"\s+", " ", texto).strip()


_probe_path = Path("/home/ubuntu/risco-urbano-probes/saida_geocoding_geosampa.json")
if _probe_path.exists():
    try:
        _PROBE_CACHE = {
            f"{normaliza(item['via'])}|{normaliza(item.get('referencia') or '')}": item
            for item in json.loads(_probe_path.read_text())["resultados"]
            if "lat" in item
        }
    except (KeyError, OSError, TypeError, ValueError):
        _PROBE_CACHE = {}


def _via(nome: str):
    if not nome:
        return None
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": CAMADA, "outputFormat": "application/json",
        "srsName": "EPSG:4326", "count": 400,
        "CQL_FILTER": f"nm_logradouro LIKE '%{nome}%'",
    }
    with httpx.Client(timeout=120) as client:
        response = client.get(WFS, params=params)
        response.raise_for_status()
    features = response.json().get("features", [])
    return unary_union([shape(feature["geometry"]) for feature in features]) if features else None


def resolve(via: str, referencia: str | None) -> dict:
    nome_via, nome_ref = normaliza(via), normaliza(referencia or "")
    geom_via = _via(nome_via)
    if geom_via is None:
        return {"metodo": "falhou"}
    geom_ref = _via(nome_ref) if nome_ref else None
    if geom_ref is None:
        point = geom_via.interpolate(0.5, normalized=True)
        return {"metodo": "centroide_da_via", "lat": point.y, "lon": point.x, "precision": "baixa"}
    inter = geom_via.intersection(geom_ref)
    if not inter.is_empty:
        point = inter.centroid
        return {"metodo": "cruzamento", "lat": point.y, "lon": point.x, "precision": "alta"}
    a, _ = nearest_points(geom_via, geom_ref)
    distance = round(a.distance(geom_ref) * 111320)
    if distance > 30:
        return {"metodo": "falhou"}
    return {"metodo": "aproximacao", "lat": a.y, "lon": a.x, "precision": "media"}


def cached_resolve(via: str, referencia: str | None) -> dict:
    key = f"{normaliza(via)}|{normaliza(referencia or '')}"
    if key in _PROBE_CACHE:
        cached = _PROBE_CACHE[key]
        return {"lat": cached["lat"], "lon": cached["lon"], "precision": cached["precisao"], "metodo": "probe-cache"}
    with connection() as conn:
        row = conn.execute("SELECT lat,lon,precision FROM geocode_cache WHERE key=?", (key,)).fetchone()
    if row:
        return {"lat": row["lat"], "lon": row["lon"], "precision": row["precision"], "metodo": "cache"}
    result = resolve(via, referencia)
    if "lat" in result:
        with connection() as conn:
            conn.execute(
                """INSERT INTO geocode_cache(key,lat,lon,precision) VALUES(?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET lat=excluded.lat,lon=excluded.lon,
                precision=excluded.precision""",
                (key, result["lat"], result["lon"], result["precision"]),
            )
    return result
