"""Sugestão de endereços enquanto a pessoa digita.

Por que isto roda no servidor e não no browser: as três fontes que o frontend
tentava estão fechadas para ele. O Places do Google responde REQUEST_DENIED
(as APIs legadas não são liberadas para projetos novos desde março/2025) e o
Nominatim bloqueia por CORS quando chamado de mapasp.com. Do servidor não há
CORS, dá para mandar User-Agent próprio — que o Nominatim exige — e dá para
guardar em cache o que todo mundo digita igual.

O motor é o Photon (OSM), que é feito para autocompletar: responde a consulta
parcial. O Nominatim entra só como reserva, porque é geocodificador e pede
endereço quase completo.
"""

import re
import time
import unicodedata
from collections import OrderedDict

import httpx

PHOTON = "https://photon.komoot.io/api/"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "MapaSP/1.0 (+https://github.com/Ceugox/mapa-risco-urbano)"

# Viés para o centro de São Paulo: o Photon ordena por relevância e distância.
CENTRO = (-23.5505, -46.6333)
# Caixa generosa (inclui Guarulhos, ABC, Osasco): quem anda pela cidade cruza
# esses limites, e um resultado em Manaus nunca ajuda.
CAIXA = (-24.15, -47.25, -23.15, -45.95)  # sul, oeste, norte, leste

MIN_CARACTERES = 2
TTL_SEGUNDOS = 600
CACHE_MAXIMO = 500

cache: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def chave(consulta: str) -> str:
    return re.sub(r"\s+", " ", _sem_acento(consulta)).strip()


def rotulo(props: dict) -> str:
    """Monta o texto que a pessoa lê na lista, sem repetir o mesmo termo."""
    rua = props.get("street") or ""
    numero = props.get("housenumber") or ""
    nome = props.get("name") or ""
    partes: list[str] = []

    if nome:
        partes.append(nome)
    if rua and rua != nome:
        partes.append(rua)
    if numero:
        partes.append(numero)

    for campo in ("district", "city"):
        valor = props.get(campo) or ""
        if valor and valor not in partes:
            partes.append(valor)
            if campo == "city":
                break
    return ", ".join(partes)


def _dentro_da_caixa(lat: float, lon: float) -> bool:
    sul, oeste, norte, leste = CAIXA
    return sul <= lat <= norte and oeste <= lon <= leste


def normaliza(payload: dict, limite: int) -> list[dict]:
    """Converte a resposta do Photon em sugestões, sem repetição.

    O OSM parte uma avenida em vários trechos, então a mesma Avenida Paulista
    volta três ou quatro vezes. Para quem está digitando, é um item só.
    """
    achados: list[dict] = []
    vistos: set[str] = set()
    for feature in payload.get("features", []):
        geometria = feature.get("geometry") or {}
        coords = geometria.get("coordinates") or []
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        if not _dentro_da_caixa(lat, lon):
            continue
        texto = rotulo(feature.get("properties") or {})
        if not texto:
            continue
        identidade = chave(texto)
        if identidade in vistos:
            continue
        vistos.add(identidade)
        props = feature.get("properties") or {}
        na_capital = chave(props.get("city") or "") == "sao paulo"
        achados.append({"label": texto, "lat": lat, "lon": lon, "_capital": na_capital})

    # O Photon ordena por relevância de texto, então "Avenida Laranjal Paulis,
    # Guarulhos" passa na frente de "Avenida Paulista" para quem digita
    # "av paulis". Quem usa o app está em São Paulo: a capital vem primeiro, e
    # dentro de cada grupo a ordem do Photon é preservada (sort é estável).
    achados.sort(key=lambda a: not a["_capital"])
    for achado in achados:
        del achado["_capital"]
    return achados[:limite]


def _photon(consulta: str, limite: int) -> list[dict]:
    resposta = httpx.get(
        PHOTON,
        params={"q": consulta, "lat": CENTRO[0], "lon": CENTRO[1], "limit": limite * 4},
        headers={"User-Agent": USER_AGENT},
        timeout=6,
    )
    resposta.raise_for_status()
    return normaliza(resposta.json(), limite)


def _nominatim(consulta: str, limite: int) -> list[dict]:
    sul, oeste, norte, leste = CAIXA
    resposta = httpx.get(
        NOMINATIM,
        params={
            "format": "json", "limit": limite, "countrycodes": "br",
            "viewbox": f"{oeste},{norte},{leste},{sul}", "bounded": 1,
            "q": consulta,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=6,
    )
    resposta.raise_for_status()
    achados = []
    for item in resposta.json():
        achados.append({
            "label": item["display_name"],
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
        })
    return achados[:limite]


def buscar(consulta: str, limite: int = 6) -> list[dict]:
    """Sugestões para uma consulta parcial. Nunca levanta: lista vazia é resposta."""
    limpa = (consulta or "").strip()
    if len(limpa) < MIN_CARACTERES:
        return []

    k = chave(limpa)
    agora = time.time()
    guardado = cache.get(k)
    if guardado and agora - guardado[0] < TTL_SEGUNDOS:
        cache.move_to_end(k)
        return guardado[1]

    achados: list[dict] = []
    for fonte in (_photon, _nominatim):
        try:
            achados = fonte(limpa, limite)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            continue
        if achados:
            break

    cache[k] = (agora, achados)
    cache.move_to_end(k)
    while len(cache) > CACHE_MAXIMO:
        cache.popitem(last=False)
    return achados
