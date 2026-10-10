from fnmatch import fnmatch
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

import httpx


@runtime_checkable
class SSRGateway(Protocol):
    async def render(self, page: dict) -> Optional[dict]: ...

    async def healthy(self) -> bool: ...


class HttpSSRGateway:
    def __init__(
        self,
        url: str,
        timeout: float = 1.0,
        render_path: str = "/render",
        health_path: str = "/health",
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.base_url = url.rstrip("/")
        self.timeout = timeout
        self.render_path = render_path
        self.health_path = health_path
        self.transport = transport

    async def render(self, page: dict) -> Optional[dict]:
        try:
            async with self._client() as client:
                response = await client.post(self.base_url + self.render_path, json=page)
                response.raise_for_status()
                return _rendered(response.json())
        except (httpx.HTTPError, ValueError):
            return None

    async def healthy(self) -> bool:
        try:
            async with self._client() as client:
                response = await client.get(self.base_url + self.health_path)
                return response.is_success
        except httpx.HTTPError:
            return False

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)


class ViteHotFileGateway:
    render_path = "/__inertia_ssr"

    def __init__(self, hot_file: str, timeout: float = 1.0, transport: Optional[httpx.AsyncBaseTransport] = None):
        self.hot_file = hot_file
        self.timeout = timeout
        self.transport = transport

    async def render(self, page: dict) -> Optional[dict]:
        gateway = self._gateway()
        return await gateway.render(page) if gateway else None

    async def healthy(self) -> bool:
        return self._gateway() is not None

    def _gateway(self) -> Optional[HttpSSRGateway]:
        origin = self._read_origin()
        if origin is None:
            return None
        return HttpSSRGateway(origin, self.timeout, render_path=self.render_path, transport=self.transport)

    def _read_origin(self) -> Optional[str]:
        try:
            with open(self.hot_file) as file:
                origin = file.read().strip().rstrip("/")
        except OSError:
            return None
        return origin or None


def _rendered(payload: Any) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("body"), str):
        raise ValueError("Invalid Inertia SSR response")
    return {"body": payload["body"], "head": payload.get("head", [])}


def is_excepted(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)
