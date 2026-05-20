from contextvars import ContextVar
from typing import Optional

from fastapi import Request

# Set by InertiaMiddleware before calling the next handler so InertiaResponse
# can access the current request without it being passed explicitly.
current_request: ContextVar[Optional[Request]] = ContextVar("inertia_request", default=None)
