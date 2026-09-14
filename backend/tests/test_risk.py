import h3
import pytest
from fastapi import HTTPException

from app import db, risk
from app.db import distance_m
from app.routers import risk as risk_router

ORIGIN = h3.latlng_to_cell(-23.5505, -46.6333, 8)
QUERY_LAT, QUERY_LON = h3.cell_to_latlng(ORIGIN)
NEIGHBOR = next(cell for cell in h3.grid_disk(ORIGIN, 1) if cell != ORIGIN)
NEIGHBOR_LAT, NEIGHBOR_LON = h3.cell_to_latlng(NEIGHBOR)
FAR = next(cell for cell in h3.grid_disk(ORIGIN, 6) if cell not in set(h3.grid_disk(ORIGIN, 1)))
FAR_LAT, FAR_LON = h3.cell_to_latlng(FAR)


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "risk.db"))
    monkeypatch.setattr(db.settings, "database_url", "")
    db.init_db()


def _point(lat: float, lon: float, **props) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


def _crime_cell(cell: str, total: int) -> dict:
    boundary = h3.cell_to_boundary(cell)
    ring = [[bound_lon, bound_lat] for bound_lat, bound_lon in boundary]
    ring.append(ring[0])
    return {
        "type": "Feature",
        "geometry": {"type": "Polygon", "coordinates": [ring]},
        "properties": {"h3": cell, "total": total},
    }


class TestSummarize:
    def test_sem_snapshots_nivel_baixo(self, tmpdb):
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        assert result == {"level": "baixo", "score": 0, "items": [], "updated_at": result["updated_at"]}
        assert result["updated_at"]

    def test_conta_por_camada_e_nivel(self, tmpdb):
        db.store_snapshot("alagamento", {"type": "FeatureCollection", "features": [
            _point(QUERY_LAT, QUERY_LON, descricao="Rua A"),
            _point(NEIGHBOR_LAT, NEIGHBOR_LON, descricao="Rua B"),
            _point(FAR_LAT, FAR_LON, descricao="Rua C fora do raio"),
        ]})
        db.store_snapshot("cemaden", {"type": "FeatureCollection", "features": [
            _point(NEIGHBOR_LAT, NEIGHBOR_LON, municipio="São Paulo"),
        ]})
        db.store_snapshot("reports", {"type": "FeatureCollection", "features": [
            _point(QUERY_LAT, QUERY_LON, category="alagamento"),
        ]})

        result = risk.summarize(QUERY_LAT, QUERY_LON)
        by_layer = {item["layer"]: item for item in result["items"]}

        assert by_layer["alagamento"]["count"] == 2
        assert by_layer["alagamento"]["nearest_m"] == 0
        assert by_layer["cemaden"]["count"] == 1
        expected_distance = round(distance_m(QUERY_LAT, QUERY_LON, NEIGHBOR_LAT, NEIGHBOR_LON))
        assert by_layer["cemaden"]["nearest_m"] == expected_distance
        assert by_layer["reports"]["count"] == 1
        assert "crime" not in by_layer

        assert result["score"] == 8 * 2 + 12 * 1 + 10 * 1
        assert result["level"] == "moderado"

    def test_crime_acima_da_media(self, tmpdb):
        db.store_snapshot("crime", {"type": "FeatureCollection", "features": [
            _crime_cell(ORIGIN, 50),
            _crime_cell(NEIGHBOR, 10),
            _crime_cell(FAR, 1),
        ]})
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        item = next(item for item in result["items"] if item["layer"] == "crime")
        assert item["count"] == 50
        assert item["label"] == "crime: célula acima da média"
        assert item["nearest_m"] == 0

    def test_crime_realista_nao_satura_o_score(self, tmpdb):
        db.store_snapshot("crime", {"type": "FeatureCollection", "features": [
            _crime_cell(ORIGIN, 300),
            _crime_cell(NEIGHBOR, 120),
            _crime_cell(FAR, 50),
        ]})
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        item = next(item for item in result["items"] if item["layer"] == "crime")
        assert item["count"] == 300
        assert result["score"] == risk.CRIME_POINTS["acima"] == 20
        assert result["level"] == "moderado"

    def test_clima_nao_conta_como_risco(self, tmpdb):
        db.store_snapshot("clima", {"type": "FeatureCollection", "features": [
            _point(QUERY_LAT, QUERY_LON, temperatura=22.5),
        ]})
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        assert result["items"] == []
        assert result["score"] == 0

    def test_inmet_conta_quando_o_poligono_cobre_o_ponto(self, tmpdb):
        big = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [QUERY_LON - 1, QUERY_LAT - 1], [QUERY_LON + 1, QUERY_LAT - 1],
                [QUERY_LON + 1, QUERY_LAT + 1], [QUERY_LON - 1, QUERY_LAT + 1],
                [QUERY_LON - 1, QUERY_LAT - 1],
            ]]},
            "properties": {"severidade": "Perigo"},
        }
        far_away = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [FAR_LON + 0.5, FAR_LAT + 0.5], [FAR_LON + 0.6, FAR_LAT + 0.5],
                [FAR_LON + 0.6, FAR_LAT + 0.6], [FAR_LON + 0.5, FAR_LAT + 0.6],
                [FAR_LON + 0.5, FAR_LAT + 0.5],
            ]]},
            "properties": {"severidade": "Perigo"},
        }
        db.store_snapshot("inmet", {"type": "FeatureCollection", "features": [big, far_away]})
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        item = next(item for item in result["items"] if item["layer"] == "inmet")
        assert item["count"] == 1
        assert result["score"] == risk.WEIGHTS["inmet"]

    def test_crime_dentro_da_media(self, tmpdb):
        db.store_snapshot("crime", {"type": "FeatureCollection", "features": [
            _crime_cell(ORIGIN, 5),
            _crime_cell(FAR, 100),
        ]})
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        item = next(item for item in result["items"] if item["layer"] == "crime")
        assert item["count"] == 5
        assert item["label"] == "crime: célula dentro da média"

    def test_ignora_snapshot_com_erro(self, tmpdb):
        db.store_snapshot(
            "alagamento", {"type": "FeatureCollection", "features": []}, ok=False, error="coleta falhou"
        )
        result = risk.summarize(QUERY_LAT, QUERY_LON)
        assert result["items"] == []
        assert result["level"] == "baixo"


class TestRouterBbox:
    def test_fora_da_bbox_retorna_422(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            risk_router.here(lat=-23.0, lon=-46.6)
        assert exc.value.status_code == 422

    def test_dentro_da_bbox_retorna_resumo(self, tmpdb):
        db.store_snapshot("reports", {"type": "FeatureCollection", "features": [
            _point(QUERY_LAT, QUERY_LON, category="alagamento"),
        ]})
        result = risk_router.here(lat=QUERY_LAT, lon=QUERY_LON)
        assert result["level"] in {"baixo", "moderado", "alto"}
        assert result["items"][0]["layer"] == "reports"
