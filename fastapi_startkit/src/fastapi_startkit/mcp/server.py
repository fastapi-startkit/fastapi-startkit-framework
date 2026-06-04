"""MCP Server base class."""

from typing import Optional, Type

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response as StarletteResponse

from .protocol import Protocol
from .request import JsonRpcRequest
from .tool import Tool
from .prompt import Prompt
from .resource import Resource


class Server:
    """Base class for MCP servers.

    Subclasses must set ``name`` and override ``tools()``, ``prompts()``,
    and/or ``resources()`` to register capabilities.

    Usage::

        class MyServer(Server):
            name = "my-server"

            def tools(self):
                return [AddTool]

        server = MyServer()
        app.include_router(server.router("/mcp"))
    """

    name: str
    description: Optional[str] = None
    instructions: Optional[str] = None

    def tools(self) -> Optional[list[Type[Tool]]]:
        """Return a list of Tool classes to register, or None."""
        return None

    def prompts(self) -> Optional[list[Type[Prompt]]]:
        """Return a list of Prompt classes to register, or None."""
        return None

    def resources(self) -> Optional[list[Type[Resource]]]:
        """Return a list of Resource classes to register, or None."""
        return None

    def router(self, prefix: str = "/mcp") -> APIRouter:
        """Build and return a FastAPI APIRouter for this server.

        The router exposes:
        - ``POST {prefix}`` — JSON-RPC 2.0 endpoint
        - ``GET {prefix}``  — returns 405 with ``Allow: POST``
        """
        protocol = Protocol(self)
        api_router = APIRouter(prefix=prefix)

        @api_router.post("")
        async def handle_post(request: Request) -> StarletteResponse:
            body = await request.json()
            rpc = JsonRpcRequest(**body)

            if rpc.is_notification:
                # Fire-and-forget: dispatch but return 202 immediately
                await protocol.dispatch(rpc.method, rpc.params, rpc.id)
                return StarletteResponse(status_code=202)

            result = await protocol.dispatch(rpc.method, rpc.params, rpc.id)
            return JSONResponse(content=result)

        @api_router.get("")
        async def handle_get() -> StarletteResponse:
            return StarletteResponse(
                status_code=405,
                headers={"Allow": "POST"},
            )

        return api_router
