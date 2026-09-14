import pytest
from pydantic import ValidationError

from app import routing
from app.routers.route import Point, RouteIn, _depart_hour


def _crime_cell(lon: float, lat: float, total: int) -> dict:
    d = 0.0012
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [lon - d, lat - d], [lon + d, lat - d], [lon + d, lat + d],
                [lon - d, lat + d], [lon - d, lat - d],
            ]],
        },
        "properties": {"total": total},
    }


def _point(lon: float, lat: float, **props) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": props,
    }


LINE = [[-46.640, -23.550], [-46.635, -23.552], [-46.630, -23.555]]


def _patch(monkeypatch, features_by_layer):
    monkeypatch.setattr(
        routing, "_features", lambda layer: features_by_layer.get(layer, [])
    )


def test_score_sem_riscos(monkeypatch):
    _patch(monkeypatch, {})
    result = routing.score_route(LINE, 900)
    assert result["score"] == 0 and result["level"] == "baixo"


def test_score_crime_pesado(monkeypatch):
    _patch(monkeypatch, {"crime": [_crime_cell(-46.635, -23.552, 500)]})
    result = routing.score_route(LINE, 900)
    assert result["breakdown"]["crime"] == 40
    assert result["level"] == "moderado"


def test_score_alagamento_e_report_seguranca(monkeypatch):
    _patch(monkeypatch, {
        "alagamento": [_point(-46.635, -23.552), _point(-46.6355, -23.5522)],
        "reports": [_point(-46.636, -23.552, category="seguranca")],
    })
    result = routing.score_route(LINE, 900)
    assert result["breakdown"]["alagamento"] > 0
    assert result["breakdown"]["reports"] == 10  # 2.0 peso / 3 → 15 * 0.66


def test_score_inmet_ativo(monkeypatch):
    _patch(monkeypatch, {"inmet": [_point(-46.0, -24.0)]})
    result = routing.score_route(LINE, 900)
    assert result["breakdown"]["inmet"] == 10


def test_ponto_distante_nao_conta(monkeypatch):
    _patch(monkeypatch, {"alagamento": [_point(-46.0, -24.0)]})
    result = routing.score_route(LINE, 900)
    assert result["breakdown"]["alagamento"] == 0


class TestTimeWeights:
    def test_driving_dia_e_baseline(self):
        weights = routing.time_weights("driving", 12)
        assert weights == routing.BASE_TIME_WEIGHTS

    def test_a_pe_dobra_crime_e_aumenta_alagamento(self):
        weights = routing.time_weights("walking", 12)
        assert weights["crime"] == pytest.approx(2.0)
        assert weights["alagamento"] == pytest.approx(4.5)
        assert weights["cemaden"] == routing.BASE_TIME_WEIGHTS["cemaden"]

    def test_noite_inicio_aumenta_crime_25_por_cento(self):
        weights = routing.time_weights("driving", 19)
        assert weights["crime"] == pytest.approx(1.25)

    def test_madrugada_aumenta_crime_50_por_cento(self):
        weights = routing.time_weights("driving", 23)
        assert weights["crime"] == pytest.approx(1.5)
        weights_cedo = routing.time_weights("driving", 4)
        assert weights_cedo["crime"] == pytest.approx(1.5)

    def test_a_pe_de_madrugada_acumula_multiplicadores(self):
        weights = routing.time_weights("walking", 23)
        assert weights["crime"] == pytest.approx(1.0 * 2.0 * 1.5)


def test_score_route_normaliza_pesos_customizados_para_100(monkeypatch):
    _patch(monkeypatch, {"crime": [_crime_cell(-46.635, -23.552, 500)]})
    weights = routing.time_weights("walking", 23)
    result = routing.score_route(LINE, 900, weights=weights)
    total = sum(weights.values())
    esperado = round(weights["crime"] * (100.0 / total) * 1.0)
    assert result["breakdown"]["crime"] == esperado
    assert result["score"] <= 100


def test_fetch_routes_usa_url_e_user_agent_por_modo(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        return FakeResponse()

    monkeypatch.setattr(routing.httpx, "get", fake_get)

    routing.fetch_routes((-23.55, -46.63), (-23.56, -46.64), mode="walking")
    assert calls[-1]["url"].startswith(routing.settings.osrm_walking_url)
    assert calls[-1]["headers"]["User-Agent"] == routing.USER_AGENT

    routing.fetch_routes((-23.55, -46.63), (-23.56, -46.64), mode="driving")
    assert calls[-1]["url"].startswith(routing.settings.osrm_driving_url)


class TestDepartHour:
    def test_sem_depart_at_usa_agora_em_sao_paulo(self):
        hour = _depart_hour(None)
        assert 0 <= hour <= 23

    def test_iso_com_fuso_e_convertido_para_sao_paulo(self):
        # 23h em UTC == 20h em São Paulo (UTC-3)
        hour = _depart_hour("2026-09-14T23:00:00+00:00")
        assert hour == 20

    def test_iso_naive_e_tratado_como_sao_paulo(self):
        hour = _depart_hour("2026-09-14T20:00:00")
        assert hour == 20

    def test_iso_invalido_gera_422(self):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            _depart_hour("não é uma data")
        assert exc.value.status_code == 422


def test_mode_invalido_rejeitado_pelo_pydantic():
    with pytest.raises(ValidationError):
        RouteIn(
            origin=Point(lat=-23.5, lon=-46.6),
            destination=Point(lat=-23.55, lon=-46.65),
            mode="bicicleta",
        )
