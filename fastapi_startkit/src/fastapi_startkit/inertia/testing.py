import html
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Optional, Self

from starlette.types import ASGIApp, Receive, Scope, Send

from fastapi_startkit.inertia.constant import Header

MISSING: Any = object()
SCRIPT_PAGE = re.compile(r"<script\b[^>]*\bdata-page=[\"'][^\"']*[\"'][^>]*>(.*?)</script>", re.DOTALL)
ATTRIBUTE_PAGE = re.compile(r"\bdata-page=(?:\"([^\"]*)\"|'([^']*)')")


class FakeSessionMiddleware:
    def __init__(self, app: ASGIApp, session: Optional[dict] = None):
        self.app = app
        self.session = session if session is not None else {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            scope["session"] = self.session
        await self.app(scope, receive, send)


def response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    body = getattr(response, "body", b"")
    return body.decode() if isinstance(body, bytes) else str(body)


def is_json(response: Any) -> bool:
    return bool(response.headers.get(Header.INERTIA)) or "json" in response.headers.get("content-type", "")


def extract_page(response: Any) -> dict:
    text = response_text(response)
    if is_json(response):
        return json.loads(text)
    script = SCRIPT_PAGE.search(text)
    if script:
        return json.loads(script.group(1))
    attribute = ATTRIBUTE_PAGE.search(text)
    if attribute:
        return json.loads(html.unescape(attribute.group(1) or attribute.group(2)))
    raise AssertionError(f"Response does not contain an Inertia page: {text[:200]!r}")


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def lookup(value: Any, path: str) -> Any:
    for segment in path.split("."):
        if isinstance(value, Mapping) and segment in value:
            value = value[segment]
        elif isinstance(value, Sequence) and not isinstance(value, str) and segment.isdigit():
            if int(segment) >= len(value):
                return MISSING
            value = value[int(segment)]
        else:
            return MISSING
    return value


class AssertablePage:
    def __init__(self, page: dict):
        self.page = page

    @classmethod
    def from_response(cls, response: Any) -> "AssertablePage":
        return cls(extract_page(response))

    @property
    def props(self) -> dict:
        return self.page.get("props", {})

    def prop(self, path: str) -> Any:
        value = lookup(self.props, path)
        ensure(value is not MISSING, f"Expected prop {path!r} to exist in props {self.props!r}")
        return value

    def component(self, name: str) -> Self:
        actual = self.page.get("component")
        ensure(actual == name, f"Expected component {name!r}, got {actual!r}")
        return self

    def url(self, url: str) -> Self:
        actual = self.page.get("url")
        ensure(actual == url, f"Expected url {url!r}, got {actual!r}")
        return self

    def version(self, version: str) -> Self:
        actual = self.page.get("version")
        ensure(actual == version, f"Expected version {version!r}, got {actual!r}")
        return self

    def has(self, path: str) -> Self:
        self.prop(path)
        return self

    def has_count(self, path: str, count: int) -> Self:
        value = self.prop(path)
        size = len(value) if isinstance(value, (Mapping, Sequence)) and not isinstance(value, str) else None
        ensure(size == count, f"Expected prop {path!r} to have {count} items, got {size}")
        return self

    def missing(self, path: str) -> Self:
        value = lookup(self.props, path)
        ensure(value is MISSING, f"Expected prop {path!r} to be missing, got {value!r}")
        return self

    def equals(self, path: str, expected: Any) -> Self:
        value = self.prop(path)
        ensure(value == expected, f"Expected prop {path!r} to equal {expected!r}, got {value!r}")
        return self

    def deferred(self, group: str, props: Sequence[str]) -> Self:
        groups = self.page.get("deferredProps", {})
        actual = groups.get(group)
        ensure(
            actual is not None and sorted(actual) == sorted(props),
            f"Expected deferred group {group!r} to be {sorted(props)!r}, got {actual!r} in {groups!r}",
        )
        return self

    def flash(self, key: str, value: Any = MISSING) -> Self:
        flash = self.page.get("flash", {})
        ensure(key in flash, f"Expected flash {key!r} to exist in {flash!r}")
        if value is not MISSING:
            ensure(flash[key] == value, f"Expected flash {key!r} to equal {value!r}, got {flash[key]!r}")
        return self


def assert_inertia(response: Any) -> AssertablePage:
    return AssertablePage.from_response(response)
