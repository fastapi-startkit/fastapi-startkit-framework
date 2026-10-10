import warnings
from typing import Optional, MutableMapping

from starlette.requests import Request


class ArraySession(dict):
    pass


class InertiaSessionWarning(UserWarning):
    pass


def session_for_queue(request: Request, what: str) -> Optional[MutableMapping]:
    session = request.scope.get("session")
    if session is None:
        warnings.warn(
            f"Inertia {what} was queued without a session and will not reach the next page. "
            "Add SessionMiddleware, or pass a session to InertiaMiddleware.",
            InertiaSessionWarning,
            stacklevel=3,
        )
    return session
