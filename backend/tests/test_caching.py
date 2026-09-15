from app import caching


class TestCacheControlPorCaminho:
    def test_html_nunca_e_reusado_sem_revalidar(self):
        # O HTML aponta para assets com hash no nome. Servir HTML velho manda o
        # browser pedir um arquivo que o deploy novo ja apagou, e o app nao sobe.
        assert caching.cache_control("/") == caching.SEM_CACHE
        assert caching.cache_control("/index.html") == caching.SEM_CACHE
        assert caching.cache_control("/admin") == caching.SEM_CACHE
        assert caching.cache_control("/t/abc123") == caching.SEM_CACHE

    def test_service_worker_e_manifest_revalidam_sempre(self):
        # sw.js em cache longo atrasa a atualizacao do proprio cache do app.
        assert caching.cache_control("/sw.js") == caching.SEM_CACHE
        assert caching.cache_control("/manifest.webmanifest") == caching.SEM_CACHE

    def test_asset_com_hash_pode_ficar_para_sempre(self):
        assert caching.cache_control("/assets/index-BN4uJKmv.js") == caching.IMUTAVEL
        assert caching.cache_control("/assets/index-73KEkM7y.css") == caching.IMUTAVEL

    def test_icone_e_imagem_tem_prazo_medio(self):
        assert caching.cache_control("/icons/icon-192.png") == caching.MEDIO
        assert caching.cache_control("/apple-touch-icon.png") == caching.MEDIO

    def test_api_nao_recebe_cabecalho_daqui(self):
        # Resposta de API tem a propria politica; este middleware nao opina.
        assert caching.cache_control("/api/layers") is None
        assert caching.cache_control("/health") is None


class TestMiddleware:
    def _envia(self, path, status=200, headers=None):
        enviado = []

        async def app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": status,
                "headers": headers or [(b"content-type", b"text/html")],
            })
            await send({"type": "http.response.body", "body": b""})

        async def send(message):
            enviado.append(message)

        async def receive():
            return {"type": "http.request"}

        import asyncio

        middleware = caching.CacheHeadersMiddleware(app)
        asyncio.run(middleware({"type": "http", "method": "GET", "path": path}, receive, send))
        inicio = enviado[0]
        return {k.decode().lower(): v.decode() for k, v in inicio["headers"]}

    def test_poe_no_html(self):
        assert self._envia("/")["cache-control"] == caching.SEM_CACHE

    def test_poe_no_asset(self):
        assert self._envia("/assets/x-abc123.js")["cache-control"] == caching.IMUTAVEL

    def test_nao_toca_na_api(self):
        assert "cache-control" not in self._envia("/api/layers")

    def test_substitui_cabecalho_de_upstream(self):
        # O proxy injeta max-age=14400 no sw.js; o nosso tem de vencer.
        cabecalhos = self._envia(
            "/sw.js", headers=[(b"content-type", b"text/javascript"), (b"cache-control", b"max-age=14400")]
        )
        assert cabecalhos["cache-control"] == caching.SEM_CACHE

    def test_ignora_requisicao_que_nao_e_http(self):
        import asyncio

        chamou = []

        async def app(scope, receive, send):
            chamou.append(scope["type"])

        middleware = caching.CacheHeadersMiddleware(app)
        asyncio.run(middleware({"type": "lifespan"}, None, None))
        assert chamou == ["lifespan"]
