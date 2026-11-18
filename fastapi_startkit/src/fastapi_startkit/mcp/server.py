"""MCP Server base class."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response as StarletteResponse
from fastapi_startkit.exceptions import ValidationException
from fastapi_startkit.exceptions.handler import ExceptionHandler

from .exceptions import INVALID_REQUEST, PARSE_ERROR, McpExceptionHandler
from .protocol import Protocol
from .request import JsonRpcRequest
from .tool import Tool
from .prompt import Prompt
from .resource import Resource

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
            try:
                rpc = await JsonRpcRequest.validate_input(body)
            except ValidationException as error:
                return rejected(INVALID_REQUEST, error.bag.summary(), error.bag.messages)
            if rpc.is_notification:
                return StarletteResponse(status_code=202)
            return JSONResponse(content=await protocol.dispatch(rpc.method, rpc.params, rpc.id))

        @api_router.api_route("", methods=NON_POST_METHODS)
        async def handle_other_methods() -> StarletteResponse:
            return StarletteResponse(status_code=405, headers={"Allow": "POST"})

        return api_router


def rejected(code: int, message: str, data: Any = None) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse({"jsonrpc": "2.0", "id": None, "error": error}, status_code=400)
