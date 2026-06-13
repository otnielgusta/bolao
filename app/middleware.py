"""Security middleware: same-origin enforcement for writes + response headers."""
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Non-browser server-to-server endpoints (token-authenticated) are exempt.
CSRF_EXEMPT_PREFIXES = ("/internal/",)


def add_security_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def _security(request: Request, call_next):
        # --- CSRF: reject cross-origin state-changing requests ---
        if request.method in UNSAFE_METHODS and not request.url.path.startswith(
            CSRF_EXEMPT_PREFIXES
        ):
            origin = request.headers.get("origin")
            if origin:
                if urlparse(origin).netloc != request.url.netloc:
                    return PlainTextResponse("Origem inválida.", status_code=403)
            else:
                # No Origin: fall back to Referer when present.
                referer = request.headers.get("referer")
                if referer and urlparse(referer).netloc != request.url.netloc:
                    return PlainTextResponse("Origem inválida.", status_code=403)

        response = await call_next(request)

        # --- Security headers (defense in depth) ---
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        if settings.cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response
