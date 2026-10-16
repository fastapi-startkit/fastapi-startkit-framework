from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_startkit.mcp import Server, Tool
from fastapi_startkit_auth import AuthError, InsufficientScope
from fastapi_startkit_auth.dependencies import current_context
from fastapi_startkit_auth.guards.guard import AuthContext

from config.mcp import McpConfig


class MissingToolScope(InsufficientScope):
    def __init__(self, tool: type[Tool]) -> None:
        self.scopes: list[str] = tool.scopes
        super().__init__(f"The {tool.name} tool requires: {' '.join(tool.scopes)}.")


def protected_resource_router(config: McpConfig) -> APIRouter:
    router = APIRouter()

    @router.get("/.well-known/oauth-protected-resource")
    @router.get(f"/.well-known/oauth-protected-resource{config.path}")
    async def protected_resource_metadata() -> dict:
        return {
            "resource": config.resource,
            "authorization_servers": [config.app_url],
            "scopes_supported": list(config.scopes),
            "bearer_methods_supported": ["header"],
        }

    return router


def bearer_challenge(config: McpConfig):
    async def handler(request: Request, error: AuthError) -> JSONResponse:
        params = [f'resource_metadata="{config.resource_metadata_url}"']
        if isinstance(error, MissingToolScope):
            params += ['error="insufficient_scope"', f'scope="{" ".join(error.scopes)}"']
        elif request.headers.get("authorization"):
            params.append('error="invalid_token"')
        return JSONResponse(
            error.to_dict(),
            status_code=error.status_code,
            headers={"WWW-Authenticate": f"Bearer {', '.join(params)}", "Cache-Control": "no-store"},
        )

    return handler


def authorize_tool_call(server: Server):
    tools = {tool.name: tool for tool in server.tools() or []}

    async def dependency(request: Request, context: AuthContext = Depends(current_context)) -> AuthContext:
        message = await request.json()
        if isinstance(message, dict) and message.get("method") == "tools/call":
            tool = tools.get((message.get("params") or {}).get("name"))
            if tool is not None and not context.can_all(tool.scopes):
                raise MissingToolScope(tool)
        return context

    return dependency
