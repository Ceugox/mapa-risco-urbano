"""Redireciona hosts alternativos (www, domínio do Railway) para o canônico.

Ativo só quando ``CANONICAL_HOST`` está definido. ``/health`` fica de fora
porque o health check do Railway chega por outro host.
"""

from urllib.parse import quote

from starlette.types import ASGIApp, Receive, Scope, Send

from .config import settings

SKIP_PATHS = ("/health",)


def redirect_target(host: str, path: str, query: str) -> str | None:
    canonical = settings.canonical_host.strip().lower()
    if not canonical:
        return None
    host = host.split(":", 1)[0].lower()
    if not host or host == canonical or path.startswith(SKIP_PATHS):
        return None
    if host.endswith(".railway.internal") or host in ("localhost", "127.0.0.1"):
        return None
    url = f"https://{canonical}{quote(path)}"
    return f"{url}?{query}" if query else url


class CanonicalHostMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode(errors="ignore") for k, v in scope.get("headers", [])}
        target = redirect_target(
            headers.get("host", ""), scope.get("path", "/"), scope.get("query_string", b"").decode()
        )
        if target is None:
            await self.app(scope, receive, send)
            return
        # 308 preserva método e corpo (um POST vindo do host antigo não vira GET).
        status = 301 if scope.get("method") in ("GET", "HEAD") else 308
        await send({
            "type": "http.response.start", "status": status,
            "headers": [(b"location", target.encode()), (b"content-length", b"0")],
        })
        await send({"type": "http.response.body", "body": b""})
