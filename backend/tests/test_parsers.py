import json
from pathlib import Path

from app.collectors.cemaden import transform
from app.collectors.cge import parse_pontos
from app.collectors.geocoding import normaliza
from app.routers.reports import BBOX

ROOT = Path(__file__).parent / "fixtures"


def test_cge_parser():
    points = parse_pontos((ROOT / "alag.html").read_text())
    assert len(points) == 17


def test_cemaden_transform():
    payload = json.loads((ROOT / "cemaden_alertas.json").read_text())
    result = transform(payload)
    assert result["features"]
    assert all(f["geometry"]["type"] == "Point" for f in result["features"])
    assert all(f["properties"]["municipio"] for f in result["features"])


def test_normaliza():
    assert normaliza("AV. JOSÉ DE ALENCAR") == "JOSE DE ALENCAR"
    assert normaliza("PTE DA CASA VERDE-JORN.WALTER ABRAHAO") == "DA CASA VERDE"
    assert normaliza("R CEL MARQUES RIBEIRO") == "MARQUES RIBEIRO"


def test_reports_bbox():
    assert BBOX[0] <= -23.55 <= BBOX[2]
    assert BBOX[1] <= -46.63 <= BBOX[3]
    assert not (BBOX[0] <= -22.0 <= BBOX[2] and BBOX[1] <= -46.63 <= BBOX[3])
