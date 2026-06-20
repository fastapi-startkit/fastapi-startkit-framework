from contextvars import ContextVar
from typing import Optional

from starlette.requests import Request

# Holds the request currently being handled so helpers such as the Vite
# `template()` view renderer can resolve it without it being passed explicitly.
# Set by RequestContextMiddleware for the duration of each request.
current_request: ContextVar[Optional[Request]] = ContextVar("current_request", default=None)
