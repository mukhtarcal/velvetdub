"""Protects the local API from web pages the user happens to have open.

The server only listens on localhost, but a malicious page could still try to talk to it:

* DNS rebinding makes the browser send requests to localhost under the attacker's hostname,
  so the Host header must be one we expect.
* A cross-site page can send simple POSTs without a preflight, so every state-changing request
  must carry a custom header. A cross-site page cannot add one without our (absent) CORS
  approval.
"""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CLIENT_HEADER = "x-velvetdub-client"


class LocalOnlyGuard(BaseHTTPMiddleware):
    def __init__(self, app: object, allowed_hosts: list[str]) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._allowed = {h.lower() for h in allowed_hosts}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        host = request.headers.get("host", "").rsplit(":", 1)[0].lower()
        if host not in self._allowed:
            return JSONResponse({"detail": "Host not allowed"}, status_code=403)
        if request.method in UNSAFE_METHODS and CLIENT_HEADER not in request.headers:
            return JSONResponse({"detail": "Missing client header"}, status_code=403)
        return await call_next(request)
