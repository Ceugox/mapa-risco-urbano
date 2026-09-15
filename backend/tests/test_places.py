from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

from app import places
from app.routers import places as places_router

REQ = SimpleNamespace(client=SimpleNamespace(host="test-ip"), headers={})


def _feature(name=None, street=None, city="São Paulo", state="São Paulo", lat=-23.55, lon=-46.63, osm_key="highway"):
    return {
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {
            "name": name, "street": street, "city": city, "state": state,
            "country": "Brasil", "osm_key": osm_key, "housenumber": None,
        },
    }


@pytest.fixture(autouse=True)
def limpa_estado():
    places.cache.clear()
    places_router.rate.clear()


class TestRotulo:
    def test_rua_com_bairro_e_cidade(self):
        rotulo = places.rotulo({"name": "Rua Augusta", "district": "Consolação", "city": "São Paulo"})
        assert rotulo == "Rua Augusta, Consolação, São Paulo"

    def test_estabelecimento_usa_nome_e_rua(self):
        rotulo = places.rotulo({"name": "Padaria Real", "street": "Rua Augusta", "city": "São Paulo"})
        assert rotulo == "Padaria Real, Rua Augusta, São Paulo"

    def test_numero_entra_junto_da_rua(self):
        rotulo = places.rotulo({"street": "Avenida Paulista", "housenumber": "1000", "city": "São Paulo"})
        assert rotulo == "Avenida Paulista, 1000, São Paulo"

    def test_sem_nada_devolve_vazio(self):
        assert places.rotulo({}) == ""


class TestNormalizaResposta:
    def test_descarta_duplicata_de_mesmo_logradouro(self):
        # OSM parte uma avenida em vários trechos; para quem digita, é um item só.
        payload = {"features": [
            _feature(name="Avenida Paulista"),
            _feature(name="Avenida Paulista", lat=-23.561),
            _feature(name="Avenida Paulista", lat=-23.57),
            _feature(name="Rua Augusta"),
        ]}
        achados = places.normaliza(payload, limite=10)
        assert [a["label"] for a in achados] == [
            "Avenida Paulista, São Paulo",
            "Rua Augusta, São Paulo",
        ]

    def test_descarta_ponto_fora_da_area_de_sao_paulo(self):
        payload = {"features": [
            _feature(name="Rua de Manaus", city="Manaus", state="Amazonas", lat=-3.1, lon=-60.0),
            _feature(name="Rua Augusta"),
        ]}
        achados = places.normaliza(payload, limite=10)
        assert [a["label"] for a in achados] == ["Rua Augusta, São Paulo"]

    def test_capital_vem_antes_de_outro_municipio(self):
        # Quem digita "av paulis" quer a Paulista, não uma avenida em Guarulhos.
        payload = {"features": [
            _feature(name="Avenida Laranjal Paulis", city="Guarulhos", lat=-23.45, lon=-46.53),
            _feature(name="Avenida Paulista", city="São Paulo"),
        ]}
        achados = places.normaliza(payload, limite=10)
        assert [a["label"] for a in achados] == [
            "Avenida Paulista, São Paulo",
            "Avenida Laranjal Paulis, Guarulhos",
        ]

    def test_ordem_do_photon_preservada_dentro_da_capital(self):
        payload = {"features": [
            _feature(name="Rua B", city="São Paulo"),
            _feature(name="Rua A", city="São Paulo"),
        ]}
        assert [a["label"] for a in places.normaliza(payload, limite=10)] == [
            "Rua B, São Paulo",
            "Rua A, São Paulo",
        ]

    def test_respeita_o_limite(self):
        payload = {"features": [_feature(name=f"Rua {i}") for i in range(20)]}
        assert len(places.normaliza(payload, limite=6)) == 6

    def test_feature_sem_coordenada_e_ignorada(self):
        payload = {"features": [{"properties": {"name": "Sem geometria"}}, _feature(name="Rua Augusta")]}
        assert [a["label"] for a in places.normaliza(payload, limite=5)] == ["Rua Augusta, São Paulo"]


class TestBusca:
    def test_usa_photon_e_guarda_em_cache(self, monkeypatch):
        chamadas = []

        def falso_get(url, params=None, headers=None, timeout=None):
            chamadas.append(params["q"])
            return httpx.Response(
                200,
                json={"features": [_feature(name="Rua Augusta")]},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(places.httpx, "get", falso_get)
        primeiro = places.buscar("rua augu")
        segundo = places.buscar("rua augu")
        assert primeiro == segundo
        assert [a["label"] for a in primeiro] == ["Rua Augusta, São Paulo"]
        assert chamadas == ["rua augu"], "a segunda chamada tinha de sair do cache"

    def test_cai_para_nominatim_quando_photon_falha(self, monkeypatch):
        def falso_get(url, params=None, headers=None, timeout=None):
            if "photon" in url:
                raise httpx.ConnectError("sem rede")
            return httpx.Response(
                200,
                json=[{"lat": "-23.55", "lon": "-46.63", "display_name": "Rua Augusta, São Paulo"}],
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(places.httpx, "get", falso_get)
        achados = places.buscar("rua augu")
        assert achados and achados[0]["label"].startswith("Rua Augusta")

    def test_as_duas_fontes_fora_do_ar_devolve_lista_vazia(self, monkeypatch):
        def falso_get(url, params=None, headers=None, timeout=None):
            raise httpx.ConnectError("sem rede")

        monkeypatch.setattr(places.httpx, "get", falso_get)
        assert places.buscar("rua augu") == []

    def test_consulta_curta_nao_sai_para_a_rede(self, monkeypatch):
        def nao_deveria(*args, **kwargs):
            raise AssertionError("não devia consultar a rede")

        monkeypatch.setattr(places.httpx, "get", nao_deveria)
        assert places.buscar("a") == []


class TestRouter:
    def test_devolve_sugestoes(self, monkeypatch):
        monkeypatch.setattr(places, "buscar", lambda q, limite=6: [{"label": "Rua Augusta, São Paulo", "lat": -23.55, "lon": -46.63}])
        resposta = places_router.suggest("rua augu", REQ)
        assert resposta["places"][0]["label"] == "Rua Augusta, São Paulo"

    def test_consulta_vazia_nao_e_erro(self, monkeypatch):
        monkeypatch.setattr(places, "buscar", lambda q, limite=6: [])
        assert places_router.suggest("", REQ) == {"places": []}

    def test_rate_limit_por_ip(self, monkeypatch):
        monkeypatch.setattr(places, "buscar", lambda q, limite=6: [])
        for _ in range(places_router.LIMITE_POR_MINUTO):
            places_router.suggest("rua", REQ)
        with pytest.raises(HTTPException) as exc:
            places_router.suggest("rua", REQ)
        assert exc.value.status_code == 429
