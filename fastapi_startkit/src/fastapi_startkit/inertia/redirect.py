from typing import Any, Dict, Optional, Self, Union
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import RedirectResponse

from fastapi_startkit.inertia import session
from fastapi_startkit.inertia.errors import ErrorsInput


def same_origin_referer(request: Optional[Request], fallback: str = "/") -> str:
    referer = request.headers.get("referer") if request is not None else None
    if not referer or request is None:
        return fallback
    target = urlsplit(referer)
    if not target.scheme and not target.netloc:
        return referer if referer.startswith("/") and not referer.startswith("//") else fallback
    origin = urlsplit(str(request.base_url))
    if (target.scheme, target.netloc) == (origin.scheme, origin.netloc):
        return referer
    return fallback


class InertiaRedirect(RedirectResponse):
    def with_errors(self, errors: ErrorsInput) -> Self:
        session.with_errors(errors)
        return self

    def with_errors_in(self, bag: str, errors: ErrorsInput) -> Self:
        session.with_errors(errors, bag)
        return self

    def flash(self, key: Union[str, Dict[str, Any]], value: Any = None) -> Self:
        session.flash(key, value)
        return self

    def clear_history(self) -> Self:
        session.clear_history()
        return self

    def preserve_fragment(self) -> Self:
        session.preserve_fragment()
        return self
