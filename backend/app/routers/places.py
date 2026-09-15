import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from .. import places
from ..netutil import client_ip

router = APIRouter(prefix="/api/places")
rate: dict[str, deque[float]] = defaultdict(deque)

# Cada tecla digitada não vira uma requisição (o front espera a pausa), mas uma
# pessoa buscando origem e destino gasta dezenas por minuto. O teto protege as
# fontes públicas sem atrapalhar uso normal.
LIMITE_POR_MINUTO = 60


def _throttle(ip: str) -> None:
    agora = time.time()
    while rate[ip] and rate[ip][0] < agora - 60:
        rate[ip].popleft()
    if len(rate[ip]) >= LIMITE_POR_MINUTO:
        raise HTTPException(429, "muitas buscas — aguarde um instante")
    rate[ip].append(agora)


@router.get("/suggest")
def suggest(q: str = "", request: Request = None):
    _throttle(client_ip(request))
    return {"places": places.buscar(q)}
