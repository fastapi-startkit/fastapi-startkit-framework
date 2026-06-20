from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from fastapi_startkit.fastapi.context import current_request


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Expose the active request through a ContextVar for the request lifetime.

    Lets helpers that have no access to the handler signature (e.g. the Vite
    ``template()`` view renderer) resolve the current request implicitly.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        token = current_request.set(request)
        try:
            return await call_next(request)
        finally:
            current_request.reset(token)
