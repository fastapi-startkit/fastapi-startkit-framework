from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_startkit.mcp import Server, Tool
from fastapi_startkit_auth import AuthException, MissingScopeException
from fastapi_startkit_auth.dependencies import current_context
from fastapi_startkit_auth.guards.guard import AuthContext

from config.mcp import McpConfig


class MissingToolScope(MissingScopeException):
    def __init__(self, tool: type[Tool], scopes: list[str]) -> None:
        self.scopes = scopes
        super().__init__(f"The {tool.name} tool requires: {' '.join(scopes)}.")


class McpServerException(Exception):
    code: int
    message: str

    def to_dict(self) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": self.code, "message": self.message},
        }


class ParseError(McpServerException):
    code = -32700
    message = "Parse error"


class InvalidRequest(McpServerException):
    code = -32600
    message = "Invalid Request"


def protected_resource_router(config: McpConfig, scopes: list[str]) -> APIRouter:
    router = APIRouter()

    @router.get("/.well-known/oauth-protected-resource")
    @router.get(f"/.well-known/oauth-protected-resource{config.path}")
    async def protected_resource_metadata() -> dict:
        return {
            "resource": config.resource,
            "authorization_servers": [config.app_url],
            "scopes_supported": scopes,
            "bearer_methods_supported": ["header"],
        }

    return router


def bearer_challenge(config: McpConfig):
    async def handler(request: Request, error: AuthException) -> JSONResponse:
        params = {"resource_metadata": config.resource_metadata_url}
        if isinstance(error, MissingToolScope):
            params |= {"error": "insufficient_scope", "scope": " ".join(error.scopes)}
        elif request.headers.get("authorization"):
            params |= {"error": "invalid_token"}

        challenge = ", ".join(f'{name}="{value}"' for name, value in params.items())
        return JSONResponse(
            error.to_dict(),
            status_code=error.status_code,
            headers={
                "WWW-Authenticate": f"Bearer {challenge}",
                "Cache-Control": "no-store",
            },
        )

    return handler


async def json_rpc_error(request: Request, error: McpServerException) -> JSONResponse:
    return JSONResponse(error.to_dict(), status_code=400)


async def read_message(request: Request) -> dict:
    try:
        message = await request.json()
    except ValueError:
        raise ParseError from None
    if not isinstance(message, dict):
        raise InvalidRequest
    return message


def called_tool(message: dict, tools: dict[str, type[Tool]]) -> type[Tool] | None:
    if message.get("method") != "tools/call":
        return None
    return tools.get((message.get("params") or {}).get("name"))


def authorize_tool_call(server: Server):
    tools = {tool.name: tool for tool in server.tools() or []}

    async def dependency(
        request: Request, context: AuthContext = Depends(current_context)
    ) -> AuthContext:
        tool = called_tool(await read_message(request), tools)
        scopes = getattr(tool, "scopes", [])
        if tool is not None and not context.can_all(scopes):
            raise MissingToolScope(tool, scopes)
        return context

    return dependency
