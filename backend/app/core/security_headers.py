"""Browser-facing safety headers on every response.

This API only returns JSON and images, so the policy can be strict. The headers mostly protect people
who open an API address directly or embed it, and they stop a browser guessing at content types.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The interactive docs (development only) load scripts and styles from a CDN, so they get no CSP.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_ONE_YEAR = 31_536_000


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, production: bool = False):
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope["path"]

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"  # never let a browser guess a file's type
                headers["X-Frame-Options"] = "DENY"  # nothing from this API belongs inside a frame
                headers["Referrer-Policy"] = "no-referrer"
                if not path.startswith(_DOCS_PATHS):
                    headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
                if path.startswith("/admin"):
                    # Admin answers hold clients' personal details: keep them out of every cache.
                    headers["Cache-Control"] = "no-store"
                if self.production:
                    # Tell browsers to use HTTPS only. Harmless over plain HTTP, where browsers ignore it.
                    headers["Strict-Transport-Security"] = f"max-age={_ONE_YEAR}"
            await send(message)

        await self.app(scope, receive, send_with_headers)
