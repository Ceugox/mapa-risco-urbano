import hashlib
import re
import time
import unicodedata
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone

import httpx
from shapely.geometry import shape

from .collectors.geocoding import cached_resolve
from .db import corroborate_report, find_nearby_report, insert_report
from .routers.reports import BBOX
from .text import TIPOS, normaliza

WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
CORROBORATE_RADIUS_M = 400.0
CORROBORATE_WINDOW_H = 3.0
DEDUP_WINDOW_S = 600.0

KEYWORDS: dict[str, list[str]] = {
    "seguranca": [
        r"assalt", r"roub", r"arrast[aã]o", r"tiroteio", r"disparo", r"\btiros?\b",
        r"furt", r"sequestr", r"\bfac[aã]o\b", r"armad[oa]", r"tentativa de assalto",
    ],
    "alagamento": [
        r"alag", r"enchente", r"inunda", r"[aá]gua na pista", r"enxurrada",
        r"[aá]gua subiu", r"boca de lobo", r"intransit[aá]vel",
    ],
    "transito": [
        r"engarraf", r"lentid[aã]o", r"acidente", r"batida", r"colis[aã]o",
        r"interdit", r"via fechada", r"atropel", r"tr[âa]nsito (?:parado|travado|lento)",
    ],
    "clima": [
        r"temporal", r"chuva forte", r"granizo", r"[aá]rvore ca[ií]da",
        r"queda de [aá]rvore", r"vento derrub", r"trovoada", r"deslizamento",
    ],
}

STREET_TYPES = (
    r"(?:avenida|av\.?|rua|r\.?|marginal|marg\.?|estrada|estr\.?|rodovia|rod\.?|"
    r"pra[cç]a|pca\.?|ponte|pte\.?|viaduto|vd\.?|largo|lgo\.?|alameda|al\.?|"
    r"travessa|trav\.?|t[uú]nel|ladeira|ld\.?)"
)
_NAME = r"[\w'.\- ]{2,45}"
_BOUNDARY = (
    r"(?:$|[,.;!?\n]|\s+(?:com|x|e|esquina|perto|pr[oó]ximo|altura|sentido|em frente|"
    r"n[oº°]|bairro|regi[aã]o|entre|at[eé]|lado|j[aá]|hoje|agora|urgente|galera|gente|"
    r"pessoal|cuidado|aten[çc][aã]o|moradores|aviso|alerta)\b)"
)
_PAIR_RE = re.compile(
    rf"\b({STREET_TYPES}\s+{_NAME}?)\s*,?\s*"
    rf"(?:\bcom\b|\bx\b|\+|esquina\s+(?:da|do|de|com)|\bentre\b|\be\b)\s+"
    rf"((?:{STREET_TYPES}\s+)?{_NAME}?)(?={_BOUNDARY})",
    re.IGNORECASE,
)
_MENTION_RE = re.compile(rf"\b({STREET_TYPES}\s+{_NAME}?)(?={_BOUNDARY})", re.IGNORECASE)
_LOOSE_PAIR_RE = re.compile(
    rf"(?:^|\s)(?:d[oa]s?|n[oa]s?)\s+({_NAME}?)\s*,?\s*"
    rf"(?:\bcom\b|\bx\b|\+|esquina\s+(?:da|do|de|com)|\bentre\b)\s+"
    rf"({_NAME}?)(?={_BOUNDARY})",
    re.IGNORECASE,
)
_BAIRRO_RE = re.compile(
    rf"(?:^|\s)(?:no|na|em|do|da|o|a|bairro(?:\s+de)?|regi[aã]o\s+d[oa])\s+"
    rf"([\wÀ-ÿ][\w'.\- ]{{2,25}}?)(?={_BOUNDARY}|\s+(?:est[aá]|ficou|amanheceu|inteir))",
)
_PHONE_RE = re.compile(r"(\+?\d{1,3}[\s.\-]?)?(\(?\d{2}\)?[\s.\-]?)?\d{4,5}[\s.\-]?\d{4}")
_AT_RE = re.compile(r"@\w+")

_seen: deque[tuple[str, float]] = deque()
_seen_set: set[str] = set()


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def sanitize(text: str) -> str:
    text = _AT_RE.sub("[contato]", text)
    text = _PHONE_RE.sub("[telefone]", text)
    return re.sub(r"\s+", " ", text).strip()[:280]


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 30):start]
    return bool(re.search(r"\b(sem|n[ãa]o|nenhum[as]?|nunca)\b[\w ]*$", prefix))


def classify(text: str) -> str | None:
    folded = _fold(text)
    scores: dict[str, int] = {}
    for category, patterns in KEYWORDS.items():
        score = 0
        for pattern in patterns:
            for match in re.finditer(pattern, folded):
                score += -1 if _negated(folded, match.start()) else 1
        if score > 0:
            scores[category] = score
    return max(scores, key=lambda key: scores[key]) if scores else None


def _clean_name(raw: str) -> str:
    text = normaliza(raw)
    text = re.sub(r"^(?:A|O|AS|OS|DA|DO|DE|NA|NO|EM|DOS|DAS|NAS|NOS)\s+", "", text)
    return re.sub(TIPOS, "", text).strip()


def _clean_loose(raw: str) -> str:
    text = _clean_name(raw)
    match = re.search(r".*\b(?:DA|DO|DE|DAS|DOS|NA|NO|NAS|NOS|A|O|E)\s+(.+)$", text)
    return match.group(1).strip() if match else text


def _safe_resolve(via: str, ref: str | None) -> dict:
    try:
        return cached_resolve(via, ref)
    except (httpx.HTTPError, ValueError, KeyError):
        return {"metodo": "falhou"}


_DISTRITOS: dict[str, tuple[float, float]] | None = None


def _distritos() -> dict[str, tuple[float, float]]:
    global _DISTRITOS
    if _DISTRITOS is not None:
        return _DISTRITOS
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "geoportal:distrito_municipal", "outputFormat": "application/json",
        "srsName": "EPSG:4326", "count": 200,
    }
    try:
        with httpx.Client(timeout=60) as client:
            features = client.get(WFS, params=params).json().get("features", [])
    except (httpx.HTTPError, ValueError):
        return {}
    loaded = {}
    for feature in features:
        name = feature.get("properties", {}).get("nm_distrito_municipal")
        if name:
            point = shape(feature["geometry"]).centroid
            loaded[normaliza(name)] = (point.y, point.x)
    if loaded:
        _DISTRITOS = loaded
    return loaded


def _resolve_bairro(name: str) -> dict:
    short = re.split(r"\s+(?:DE|DO|DA|DOS|DAS|E)\s+", name, maxsplit=1)[0]
    for candidate in dict.fromkeys([name, short]):
        if len(candidate) < 3:
            continue
        for official, (lat, lon) in _distritos().items():
            if candidate in official:
                return {"metodo": "distrito", "lat": lat, "lon": lon, "precision": "baixa"}
    return {"metodo": "falhou"}


def street_mentions(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    pairs, covered = [], []
    for match in _PAIR_RE.finditer(text):
        pairs.append((_clean_name(match.group(1)), _clean_name(match.group(2))))
        covered.append(match.span())
    singles = []
    for match in _MENTION_RE.finditer(text):
        if not any(start <= match.start() < end for start, end in covered):
            name = _clean_name(match.group(1))
            if name:
                singles.append(name)
    return [(a, b) for a, b in pairs if a and b], singles


def extract_location(text: str) -> dict | None:
    pairs, singles = street_mentions(text)
    loose = [
        (_clean_loose(m.group(1)), _clean_loose(m.group(2)))
        for m in _LOOSE_PAIR_RE.finditer(text)
    ]
    for via, ref in (pairs + loose)[:3]:
        result = _safe_resolve(via, ref)
        if "lat" in result:
            return {**result, "matched": f"{via} x {ref}"}
    for via in singles[:1]:
        result = _safe_resolve(via, None)
        if "lat" in result:
            return {**result, "matched": via}
    bairro = _BAIRRO_RE.search(text)
    if bairro:
        name = normaliza(bairro.group(1))
        result = _resolve_bairro(name)
        if "lat" in result:
            return {**result, "matched": name}
    return None


def _is_duplicate(digest: str) -> bool:
    now = time.time()
    while _seen and _seen[0][1] < now - DEDUP_WINDOW_S:
        _seen_set.discard(_seen.popleft()[0])
    if digest in _seen_set:
        return True
    _seen.append((digest, now))
    _seen_set.add(digest)
    return False


def ingest_text(text: str, channel: str) -> dict:
    clean = sanitize(text)
    if len(clean) < 8:
        return {"ingested": False, "reason": "texto vazio"}
    digest = hashlib.sha256(_fold(clean).encode()).hexdigest()
    if _is_duplicate(digest):
        return {"ingested": False, "reason": "duplicada"}
    category = classify(clean)
    if category is None:
        return {"ingested": False, "reason": "fora de escopo"}
    location = extract_location(clean)
    if location is None or "lat" not in location:
        return {"ingested": False, "reason": "sem localização identificada"}
    lat, lon = location["lat"], location["lon"]
    if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
        return {"ingested": False, "reason": "localização fora de São Paulo"}
    nearby = find_nearby_report(lat, lon, category, CORROBORATE_RADIUS_M, CORROBORATE_WINDOW_H)
    if nearby:
        result = corroborate_report(nearby["id"])
        if result:
            return {
                "ingested": True, "action": "corroborated", "report_id": nearby["id"],
                "category": category, "confirmations": result["confirmations"],
                "status": result["status"],
            }
    created = datetime.now(timezone.utc)
    hours = 6 if category in {"alagamento", "transito", "clima"} else 24
    report = {
        "id": uuid.uuid4().hex, "category": category, "description": clean,
        "lat": lat, "lon": lon, "created_at": created.isoformat(),
        "expires_at": (created + timedelta(hours=hours)).isoformat(),
        "confirmations": 0, "source": channel,
        "status": "pendente" if category == "seguranca" else "visivel",
    }
    insert_report(report)
    return {
        "ingested": True, "action": "created", "report_id": report["id"],
        "category": category, "status": report["status"],
        "precision": location.get("precision"), "matched": location.get("matched"),
    }
