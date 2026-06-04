from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from .protocol import Protocol
from .request import JsonRpcRequest

if TYPE_CHECKING:
    from .tool import Tool
    from .prompt import Prompt
    from .resource import Resource


class Server:
    """Base class for MCP servers.

    Subclasses set ``name``/``description``/``instructions`` and override
    ``tools()``, ``prompts()``, and ``resources()`` to return lists of the
    corresponding subclasses to register, then mount the server on a
    FastAPI app::

        class MyServer(Server):
            name = "my-server"
            def tools(self): return [MyTool]

        mcp = MyServer()
        app.include_router(mcp.router("/mcp"))
    """

    name: str | None = None
    description: str | None = None
    instructions: str | None = None

    def tools(self) -> list[type[Tool]] | None:
        """Return Tool subclasses to register."""
        return None

    def prompts(self) -> list[type[Prompt]] | None:
        """Return Prompt subclasses to register."""
        return None

    def resources(self) -> list[type[Resource]] | None:
        """Return Resource subclasses to register."""
        return None

    def schema(self) -> dict | None:
        """Optional custom server schema."""
        return None

    def middleware(self) -> list | None:
        """Optional middleware callables for request processing."""
        return None

    def capabilities(self) -> dict:
        """Build MCP capabilities dict from registered components."""
        caps: dict = {}
        if self.tools():
            caps["tools"] = {}
        if self.prompts():
            caps["prompts"] = {}
        if self.resources():
            caps["resources"] = {}
        return caps

    def _build_protocol(self) -> Protocol:
        tools = [cls() for cls in (self.tools() or [])]

        prompts = []
        for cls in self.prompts() or []:
            instance = cls()
            if instance.should_register():
                prompts.append(instance)

        resources = [cls() for cls in (self.resources() or [])]

        return (
            Protocol(self)
            .tools(tools)
            .prompts(prompts)
            .resources(resources)
        )

    def router(self, prefix: str) -> APIRouter:
        """Return a FastAPI ``APIRouter`` exposing the MCP JSON-RPC endpoints.

        Mount it with ``app.include_router(server.router("/mcp"))`` on a
        ``FastAPI`` app or any ``APIRouter``. Pass ``""`` to mount at the root.
        """
        router = APIRouter()
        protocol = self._build_protocol()
        path = prefix or "/"

        @router.post(path)
        async def handle_post(request: JsonRpcRequest):
            # Notifications (no id) — acknowledge
            if request.is_notification:
                return JSONResponse({}, status_code=202)

            result = await protocol.dispatch(
                request.method, request.id, request.params
            )
            return JSONResponse(result)

        @router.get(path)
        async def handle_get():
            return JSONResponse(
                {"error": "Use POST for JSON-RPC requests"},
                status_code=405,
                headers={"Allow": "POST"},
            )

        return router
