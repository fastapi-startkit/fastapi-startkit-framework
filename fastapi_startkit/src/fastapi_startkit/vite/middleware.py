from typing import TYPE_CHECKING, Any

from .vite import Vite

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class ViteMiddleware:
    def __init__(self, app: "ASGIApp", vite: Vite | None = None) -> None:
        self.app = app
        self.vite = vite

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> Any:
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        with self.resolve_vite().request_scope():
            return await self.app(scope, receive, send)

    def resolve_vite(self) -> Vite:
        if self.vite is None:
            from fastapi_startkit.application import app

            self.vite = app().make("vite")
        return self.vite
