from fastapi import Request


def client_ip(request: Request) -> str:
    """Primeiro salto do X-Forwarded-For (Railway) ou o IP direto."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
