"""Refuse oversized request bodies before the server reads them.

FastAPI parses a multipart body before the route code runs, so a size check inside the route comes
too late: the whole upload would already have been received and buffered. This guard looks at the
declared Content-Length and answers 413 straight away.

It can only judge what the client declares. A client that streams without declaring a length is
not stopped here; the routes still cap each file as they read it, and a reverse proxy in front of
the API should also set a request-size limit (see the deployment notes).
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.uploads import MAX_ORDER_IMAGES, MULTIPART_OVERHEAD

_TEXT_FIELDS_ALLOWANCE = 64 * 1024  # the order form's text fields
DEFAULT_BODY_LIMIT = 1024 * 1024  # 1 MB: far more than any JSON form or admin edit here needs

_BODY_METHODS = {"POST", "PUT", "PATCH"}


def body_limit_for(path: str) -> int:
    """The largest request body allowed on this path. Upload routes get room for their files;
    everything else gets a small default, so nobody can make the server read gigabytes of JSON."""
    if path == "/admin/uploads/images":
        return settings.max_upload_bytes + MULTIPART_OVERHEAD
    if path == "/enquiries/order":
        return MAX_ORDER_IMAGES * settings.max_upload_bytes + MULTIPART_OVERHEAD + _TEXT_FIELDS_ALLOWANCE
    return DEFAULT_BODY_LIMIT


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _BODY_METHODS:
            limit = body_limit_for(scope["path"])
            declared = dict(scope["headers"]).get(b"content-length", b"")
            if declared.isdigit() and int(declared) > limit:
                response = JSONResponse({"detail": "That upload is too large."}, status_code=413)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
