"""ASGI middleware that emits a structured ``RequestHandled`` event per request.

This is dispatch-only: it fires the event through the framework's existing
Event dispatcher (task #940) and does not persist, log, or render anything
itself. Consumers — a logging listener, tests, future tooling — register
listeners the normal way via ``Event.listen(RequestHandled, ...)``.

Out of scope for this middleware (left as extension points for follow-up
work): DB query watchers, exception watchers, and any other Telescope-style
watcher, plus storage/UI for the emitted events.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fastapi_startkit.events.helpers import event

from .events import RequestHandled

REQUEST_ID_HEADER = "X-Request-Id"


class RequestLifecycleMiddleware(BaseHTTPMiddleware):
    """Dispatches ``RequestHandled`` (method, path, status, duration, request id)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        started_at = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            status_code = response.status_code if response is not None else 500

            if response is not None:
                response.headers.setdefault(REQUEST_ID_HEADER, request_id)

            await event(
                RequestHandled(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                )
            )
