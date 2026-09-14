import asyncio

import pytest

from app import canonical


@pytest.fixture
def canonical_host(monkeypatch):
    monkeypatch.setattr(canonical.settings, "canonical_host", "mapasp.com")


def test_desligado_sem_variavel(monkeypatch):
    monkeypatch.setattr(canonical.settings, "canonical_host", "")
    assert canonical.redirect_target("www.mapasp.com", "/", "") is None


def test_host_canonico_nao_redireciona(canonical_host):
    assert canonical.redirect_target("mapasp.com", "/mapa", "") is None
    assert canonical.redirect_target("MAPASP.COM:443", "/", "") is None


def test_www_e_dominio_railway_redirecionam(canonical_host):
    assert canonical.redirect_target("www.mapasp.com", "/", "") == "https://mapasp.com/"
    assert (
        canonical.redirect_target("mapa-risco-urbano-production.up.railway.app", "/t/abc", "x=1")
        == "https://mapasp.com/t/abc?x=1"
    )


def test_health_e_hosts_internos_ficam_de_fora(canonical_host):
    assert canonical.redirect_target("www.mapasp.com", "/health", "") is None
    assert canonical.redirect_target("app.railway.internal", "/api/layers", "") is None
    assert canonical.redirect_target("localhost:8000", "/", "") is None


def test_middleware_responde_301_para_get_e_308_para_post(canonical_host):
    """Exercita o middleware ASGI direto, sem plugin de async.

    Com `@pytest.mark.anyio` a contagem da suíte dependia de o trio estar
    instalado ou não (109 na máquina do autor, 108 a partir do
    requirements.txt). asyncio.run mantém o resultado igual em todo ambiente.
    """
    asyncio.run(_exercita_middleware())


async def _exercita_middleware():
    sent = []

    async def app(scope, receive, send):
        raise AssertionError("app não deveria ser chamado")

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request"}

    middleware = canonical.CanonicalHostMiddleware(app)
    scope = {
        "type": "http", "method": "GET", "path": "/", "query_string": b"",
        "headers": [(b"host", b"www.mapasp.com")],
    }
    await middleware(scope, receive, send)
    assert sent[0]["status"] == 301
    assert dict(sent[0]["headers"])[b"location"] == b"https://mapasp.com/"

    sent.clear()
    await middleware({**scope, "method": "POST", "path": "/api/reports"}, receive, send)
    assert sent[0]["status"] == 308
