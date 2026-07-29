"""Structured events emitted by the FastAPI request lifecycle.

These ride on the framework's Laravel-style event dispatcher (see
``fastapi_startkit.events``) — this module only defines the event payload,
it does not dispatch, log, or persist anything itself.
"""

from dataclasses import dataclass


@dataclass
class RequestHandled:
    """Dispatched once per HTTP request by ``RequestLifecycleMiddleware``.

    Register a listener the normal way to observe it::

        from fastapi_startkit.facades import Event
        from fastapi_startkit.fastapi.events import RequestHandled

        Event.listen(RequestHandled, lambda e: logger.info(
            "%s %s -> %s (%.1fms) [%s]", e.method, e.path, e.status_code, e.duration_ms, e.request_id
        ))
    """

    method: str
    path: str
    status_code: int
    duration_ms: float
    request_id: str
