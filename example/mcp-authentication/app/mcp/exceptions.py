from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi_startkit.mcp import Tool
from fastapi_startkit_auth import AuthException, MissingScopeException

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


class McpOAuthExceptionHandler:
    def __init__(self, config: McpConfig) -> None:
        self.config = config

    async def __call__(self, request: Request, error: AuthException) -> JSONResponse:
        params = {"resource_metadata": self.config.resource_metadata_url}
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


class McpServerExceptionHandler:
    async def __call__(
        self, request: Request, error: McpServerException
    ) -> JSONResponse:
        return JSONResponse(error.to_dict(), status_code=400)
