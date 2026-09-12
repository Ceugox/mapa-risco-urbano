"""Geocodificacao correta dos pontos do CGE usando a malha viaria oficial.

O Nominatim devolve o centroide da via inteira - inutil para vias longas como a
Marginal Tiete (erro de quilometros). A malha `segmento_logradouro` do GeoSampa
(218 mil segmentos com tipo + nome) permite resolver o cruzamento real entre a
via alagada e a referencia, que e exatamente o que o CGE informa.

Estrategia: buscar os segmentos de cada via por nome, unir e intersectar.
Quando nao ha intersecao geometrica (vias proximas mas nao concorrentes, caso
comum em ponte sobre marginal), usa-se o ponto de maior aproximacao.
"""

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone

import requests
from shapely.geometry import shape
from shapely.ops import nearest_points, unary_union

WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
CAMADA = "geoportal:segmento_logradouro"

# tipo de via: o GeoSampa guarda isso em cd_tipo_logradouro, fora do nome
TIPOS = r"^(AV|AVENIDA|R|RUA|PCA|PC|PTE|VD|EST|ROD|MARG|MARGINAL|CV|TUN|TRV|AL|LGO|ACS|COMPL)\b\.?\s*"
# titulo (patente/profissao): idem, fica em cd_titulo_logradouro
TITULOS = r"^(CEL|CAP|TEN|SGT|GEN|MAL|BRIG|DR|DRA|PROF|PROFA|PE|SEN|DEP|VER|GOV|PRES|MIN|ENG|JORN|SARG|VIS|CDE|CDSSA|MAJ)\b\.?\s*"


def normaliza(texto: str) -> str:
    """Reduz o texto do CGE ao nome puro do logradouro, como o GeoSampa armazena."""
    texto = unicodedata.normalize("NFKD", texto.upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\(.*?\)", " ", texto)
    texto = re.split(r"[-–]", texto)[0]  # "CASA VERDE-JORN.WALTER ABRAHAO" -> "CASA VERDE"
    texto = re.sub(r"[.,]", " ", texto).strip()
    texto = re.sub(TIPOS, "", texto).strip()
    texto = re.sub(TITULOS, "", texto).strip()
    return re.sub(r"\s+", " ", texto).strip()


def busca_via(nome: str):
    """Retorna a geometria unificada dos segmentos cujo nome contem `nome`."""
    if not nome:
        return None
    resp = requests.get(
        WFS,
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": CAMADA,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": 400,
            "CQL_FILTER": f"nm_logradouro LIKE '%{nome}%'",
        },
        timeout=120,
    )
    resp.raise_for_status()
    feats = resp.json().get("features", [])
    if not feats:
        return None
    return unary_union([shape(f["geometry"]) for f in feats])


def resolve(via: str, referencia: str | None) -> dict:
    nome_via, nome_ref = normaliza(via), normaliza(referencia or "")
    geom_via = busca_via(nome_via)
    if geom_via is None:
        return {"metodo": "falhou", "motivo": f"via '{nome_via}' nao encontrada na malha"}

    geom_ref = busca_via(nome_ref) if nome_ref else None
    if geom_ref is None:
        p = geom_via.interpolate(0.5, normalized=True)
        return {"metodo": "centroide_da_via", "lat": p.y, "lon": p.x, "precisao": "baixa"}

    inter = geom_via.intersection(geom_ref)
    if not inter.is_empty:
        p = inter.centroid
        return {"metodo": "cruzamento", "lat": p.y, "lon": p.x, "precisao": "alta"}

    a, b = nearest_points(geom_via, geom_ref)
    dist_m = round(a.distance(b) * 111_320)
    p = a
    return {"metodo": "aproximacao", "lat": p.y, "lon": p.x, "distancia_m": dist_m, "precisao": "media"}


def main() -> int:
    with open("saida_cge.json", encoding="utf-8") as fh:
        pontos = json.load(fh)["pontos"]

    resultados = []
    for ponto in pontos:
        r = resolve(ponto["via"], ponto["referencia"])
        resultados.append({"via": ponto["via"], "referencia": ponto["referencia"], **r})

    metodos: dict[str, int] = {}
    for r in resultados:
        metodos[r["metodo"]] = metodos.get(r["metodo"], 0) + 1

    relatorio = {
        "coletado_em": datetime.now(timezone.utc).isoformat(),
        "geocodificador": "GeoSampa segmento_logradouro + shapely",
        "pontos_testados": len(resultados),
        "por_metodo": metodos,
        "precisao_alta_ou_media": sum(1 for r in resultados if r.get("precisao") in ("alta", "media")),
        "amostra": resultados[:4],
    }
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    with open("saida_geocoding_geosampa.json", "w", encoding="utf-8") as fh:
        json.dump({"relatorio": relatorio, "resultados": resultados}, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
