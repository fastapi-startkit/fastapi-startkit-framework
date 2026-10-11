from typing import Optional
from urllib.parse import urlsplit

from starlette.requests import Request


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
