from app import routing


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
