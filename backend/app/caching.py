"""Política de cache das respostas estáticas.

Por que existe: em 15/09/2026 o `index.html` era servido **sem**
`Cache-Control`. O browser aplica cache heurístico em cima do `last-modified`,
então um visitante que já tinha entrado recebia o HTML do deploy anterior, que
aponta para `assets/index-<hash>.js`. Esse arquivo não existe mais depois do
deploy seguinte: 404 no CSS e no JS, e o app simplesmente não sobe. O `sw.js`
vinha com `max-age=14400`, o que atrasava em até quatro horas a
atualização do próprio cache do PWA.

Cuidado com a borda: em 15/09/2026 o `/sw.js` chegava ao browser com
`max-age=14400, must-revalidate` apesar deste middleware, porque a Cloudflare
da zona elevava o TTL. Não era falha daqui — o app já devolvia
`no-cache, must-revalidate`. Foi resolvido pondo a zona em "Respect Existing
Headers", e o header daqui chega intacto. Se divergir de novo, compare com o
que o app responde local antes de mexer neste arquivo; ver a nota sobre domínio
no AGENTS.md.

A regra é a de sempre para site com asset versionado por hash: o HTML e os
arquivos que apontam para ele revalidam sempre; o que tem hash no nome pode
ficar guardado para sempre.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SEM_CACHE = "no-cache, must-revalidate"
IMUTAVEL = "public, max-age=31536000, immutable"
MEDIO = "public, max-age=86400"

# Arquivos que o browser precisa reconferir a cada visita, porque são a porta
# de entrada: o HTML, o service worker e o manifesto.
SEMPRE_REVALIDA = ("/sw.js", "/manifest.webmanifest")
# Rotas do app que devolvem o index.html.
PREFIXOS_HTML = ("/admin", "/t/")
# Caminhos cuja política é de quem responde, não deste middleware.
NAO_MEXER = ("/api/", "/health")

EXTENSOES_MEDIAS = (".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff2", ".woff")


def cache_control(path: str) -> str | None:
    """Valor do Cache-Control para um caminho, ou None para não opinar."""
    if path.startswith(NAO_MEXER):
        return None
    if path in SEMPRE_REVALIDA:
        return SEM_CACHE
    if path.startswith("/assets/"):
        # Vite põe o hash do conteúdo no nome; conteúdo novo é nome novo.
        return IMUTAVEL
    if path.endswith(EXTENSOES_MEDIAS):
        return MEDIO
    if path == "/" or path.endswith(".html") or path.startswith(PREFIXOS_HTML):
        return SEM_CACHE
    return SEM_CACHE


class CacheHeadersMiddleware:
    """Escreve o Cache-Control na resposta, por cima do que o proxy tenha posto."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        valor = cache_control(scope.get("path", "/"))
        if valor is None:
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (chave, conteudo)
                    for chave, conteudo in message.get("headers", [])
                    if chave.decode().lower() != "cache-control"
                ]
                headers.append((b"cache-control", valor.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
