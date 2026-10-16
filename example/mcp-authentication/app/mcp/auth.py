from fastapi import APIRouter, Depends, Request
from fastapi_startkit.mcp import Server, Tool
from fastapi_startkit_auth.dependencies import current_context
from fastapi_startkit_auth.guards.guard import AuthContext

from app.mcp.exceptions import InvalidRequest, MissingToolScope, ParseError
from config.mcp import McpConfig


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
