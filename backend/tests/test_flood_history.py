from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.routers import layers


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(db.settings, "database_url", "")
    db.init_db()


def _iso(minutes_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def _feature(lat: float = -23.55, lon: float = -46.63, via: str = "AV PAULISTA") -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"via": via},
    }


def test_dedupe_em_30_minutos(tmpdb):
    db.record_flood_points([_feature()], _iso(20))
    db.record_flood_points([_feature()], _iso(0))
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM flood_history").fetchall()
    assert len(rows) == 1


def test_nao_deduplica_apos_30_minutos(tmpdb):
    db.record_flood_points([_feature()], _iso(40))
    db.record_flood_points([_feature()], _iso(0))
    with db.connection() as conn:
        rows = conn.execute("SELECT * FROM flood_history").fetchall()
    assert len(rows) == 2


def test_contagem_de_episodios(tmpdb):
    # 3 coletas espaçadas por menos de 2h -> 1 episódio.
    for minutes_ago in (300, 260, 220):
        db.record_flood_points([_feature()], _iso(minutes_ago))
    # coleta seguinte 5h depois da última -> novo episódio.
    db.record_flood_points([_feature()], _iso(220 - 5 * 60))
    result = db.flood_recurrence(30)
    assert len(result) == 1
    assert result[0]["episodes"] == 2
    assert result[0]["name"] == "AV PAULISTA"


def test_pontos_distintos_nao_se_misturam(tmpdb):
    db.record_flood_points([_feature(via="AV PAULISTA")], _iso(10))
    db.record_flood_points([_feature(lat=-23.60, lon=-46.70, via="MARGINAL TIETE")], _iso(10))
    result = db.flood_recurrence(30)
    assert len(result) == 2


def test_geojson_da_camada(tmpdb, monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    db.record_flood_points([_feature()], now)
    payload = layers.get_layer("alagamento_hist")
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    feature = payload["features"][0]
    assert feature["geometry"]["type"] == "Point"
    props = feature["properties"]
    assert props["name"] == "AV PAULISTA"
    assert props["episodes"] == 1
    assert props["days"] == 30
    assert payload["_metadata"]["layer"] == "alagamento_hist"
    assert payload["_metadata"]["ok"] is True


def test_lista_de_camadas_inclui_alagamento_hist(tmpdb):
    db.record_flood_points([_feature()], datetime.now(timezone.utc).isoformat())
    result = layers.list_layers()
    row = next(r for r in result if r["layer"] == "alagamento_hist")
    assert row["ok"] is True
    assert row["count"] == 1


def test_retencao_apaga_linhas_com_mais_de_90_dias(tmpdb):
    with db.connection() as conn:
        old = (datetime.now(timezone.utc) - timedelta(days=95)).isoformat()
        recent = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO flood_history(key,name,lat,lon,seen_at) VALUES(?,?,?,?,?)",
            ("old|-23.5500|-46.6300", "RUA ANTIGA", -23.55, -46.63, old),
        )
        conn.execute(
            "INSERT INTO flood_history(key,name,lat,lon,seen_at) VALUES(?,?,?,?,?)",
            ("novo|-23.5500|-46.6300", "RUA NOVA", -23.55, -46.63, recent),
        )
    removed = db.purge_flood_history(90)
    assert removed == 1
    with db.connection() as conn:
        rows = conn.execute("SELECT name FROM flood_history").fetchall()
    assert [row["name"] for row in rows] == ["RUA NOVA"]
