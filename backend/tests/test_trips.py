from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import db
from app.routers import trips

REQ = SimpleNamespace(client=SimpleNamespace(host="test-ip"))
DEST = trips.DestinationIn(lat=-23.55, lon=-46.63, label="Casa")
FORA_DA_BBOX = trips.DestinationIn(lat=-22.9, lon=-43.2, label="Rio")


@pytest.fixture
def tmpdb(monkeypatch, tmp_path):
    monkeypatch.setattr(db.settings, "database_path", str(tmp_path / "t.db"))
    monkeypatch.setattr(db.settings, "database_url", "")
    db.init_db()
    trips.rate.clear()


def _create(destination=DEST, duration_min=None):
    return trips.create_trip(trips.TripIn(destination=destination, duration_min=duration_min), REQ)


class TestCreate:
    def test_cria_trajeto(self, tmpdb):
        result = _create()
        assert result["id"] and result["share_token"] and result["update_token"]
        assert result["share_token"] != result["update_token"]
        assert result["expires_at"]

    def test_duracao_maxima_720_min(self, tmpdb):
        result = _create(duration_min=10_000)
        trip = db.get_trip(result["id"])
        created = datetime.fromisoformat(trip["created_at"])
        expires = datetime.fromisoformat(trip["expires_at"])
        assert (expires - created).total_seconds() <= 720 * 60

    def test_destino_fora_da_bbox(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            _create(destination=FORA_DA_BBOX)
        assert exc.value.status_code == 422


class TestPosition:
    def test_token_errado(self, tmpdb):
        created = _create()
        with pytest.raises(HTTPException) as exc:
            trips.send_position(
                created["id"],
                trips.PositionIn(lat=-23.55, lon=-46.63, update_token="errado"),
            )
        assert exc.value.status_code == 403

    def test_posicao_fora_da_bbox(self, tmpdb):
        created = _create()
        with pytest.raises(HTTPException) as exc:
            trips.send_position(
                created["id"],
                trips.PositionIn(lat=-22.9, lon=-43.2, update_token=created["update_token"]),
            )
        assert exc.value.status_code == 422

    def test_atualiza_posicao(self, tmpdb):
        created = _create()
        trips.send_position(
            created["id"],
            trips.PositionIn(lat=-23.56, lon=-46.64, update_token=created["update_token"]),
        )
        shared = trips.shared_trip(created["share_token"])
        assert shared["last_position"] == {
            "lat": -23.56, "lon": -46.64, "at": shared["last_position"]["at"]
        }

    def test_trip_inexistente(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            trips.send_position(
                "nao-existe", trips.PositionIn(lat=-23.55, lon=-46.63, update_token="x")
            )
        assert exc.value.status_code == 404


class TestFinish:
    def test_finaliza(self, tmpdb):
        created = _create()
        trips.finish_trip(created["id"], trips.FinishIn(update_token=created["update_token"]))
        shared = trips.shared_trip(created["share_token"])
        assert shared["finished_at"] is not None
        assert shared["active"] is False

    def test_finish_token_errado(self, tmpdb):
        created = _create()
        with pytest.raises(HTTPException) as exc:
            trips.finish_trip(created["id"], trips.FinishIn(update_token="errado"))
        assert exc.value.status_code == 403


class TestShared:
    def test_get_publico_nao_expoe_update_token(self, tmpdb):
        created = _create()
        shared = trips.shared_trip(created["share_token"])
        assert "update_token" not in shared
        assert shared["destination"] == {"lat": -23.55, "lon": -46.63, "label": "Casa"}
        assert shared["last_position"] is None
        assert shared["active"] is True

    def test_share_token_inexistente(self, tmpdb):
        with pytest.raises(HTTPException) as exc:
            trips.shared_trip("nao-existe")
        assert exc.value.status_code == 404

    def test_trip_expirada(self, tmpdb):
        created = _create(duration_min=1)
        with db.connection() as conn:
            conn.execute(
                "UPDATE trips SET expires_at=? WHERE id=?",
                ("2000-01-01T00:00:00+00:00", created["id"]),
            )
        shared = trips.shared_trip(created["share_token"])
        assert shared["active"] is False
        with pytest.raises(HTTPException) as exc:
            trips.send_position(
                created["id"],
                trips.PositionIn(lat=-23.55, lon=-46.63, update_token=created["update_token"]),
            )
        assert exc.value.status_code == 410
