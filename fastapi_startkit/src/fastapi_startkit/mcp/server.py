"""MCP Server base class."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response as StarletteResponse
from pydantic import ValidationError

from fastapi_startkit.exceptions.handler import ExceptionHandler

from .exceptions import INVALID_REQUEST, PARSE_ERROR, McpExceptionHandler
from .protocol import Protocol
from .request import JsonRpcRequest
from .tool import Tool
from .prompt import Prompt
from .resource import Resource

NOTIFICATION_PREFIX = "notifications/"
NON_POST_METHODS = ["GET", "HEAD", "PUT", "PATCH", "DELETE", "OPTIONS"]


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
    description: str | None = None
    instructions: str | None = None
    exception_handler: type[ExceptionHandler] = McpExceptionHandler

    def tools(self) -> list[type[Tool]] | None:
        """Return a list of Tool classes to register, or None."""
        return None

    def prompts(self) -> list[type[Prompt]] | None:
        """Return a list of Prompt classes to register, or None."""
        return None

    def resources(self) -> list[type[Resource]] | None:
        """Return a list of Resource classes to register, or None."""
        return None

    def router(self, prefix: str = "/mcp") -> APIRouter:
        protocol = Protocol(self)
        api_router = APIRouter(prefix=prefix)

        @api_router.post("")
        async def handle_post(request: Request) -> StarletteResponse:
            try:
                body = await request.json()
            except ValueError:
                return rejected(PARSE_ERROR, "Parse error: the body is not valid JSON.")
            if not isinstance(body, dict):
                return rejected(
                    INVALID_REQUEST, "Invalid request: send one JSON-RPC request object; batches are not supported."
                )
            try:
                rpc = JsonRpcRequest.model_validate(body)
            except ValidationError:
                return rejected(INVALID_REQUEST, "Invalid request: expected a JSON-RPC 2.0 request object.")
            if rpc.is_notification:
                if rpc.method.startswith(NOTIFICATION_PREFIX):
                    return StarletteResponse(status_code=202)
                return rejected(INVALID_REQUEST, f"Invalid request: {rpc.method} needs an id.")
            return JSONResponse(content=await protocol.dispatch(rpc.method, rpc.params, rpc.id))

        @api_router.api_route("", methods=NON_POST_METHODS)
        async def handle_other_methods() -> StarletteResponse:
            return StarletteResponse(status_code=405, headers={"Allow": "POST"})

        return api_router


def rejected(code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": None, "error": {"code": code, "message": message}},
        status_code=400,
    )
