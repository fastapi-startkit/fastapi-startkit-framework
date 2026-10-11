from typing import Optional

from starlette.types import ASGIApp, Receive, Scope, Send


class FakeSessionMiddleware:
    def __init__(self, app: ASGIApp, session: Optional[dict] = None):
        self.app = app
        self.session = session if session is not None else {}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            scope["session"] = self.session
        await self.app(scope, receive, send)
