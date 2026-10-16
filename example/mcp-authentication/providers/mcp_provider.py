from fastapi import Depends
from fastapi_startkit.support import Provider
from fastapi_startkit_auth import (
    AuthenticationException,
    InvalidTokenException,
    MissingScopeException,
)

from app.commands.create_client import CreateClientCommand
from app.mcp.auth import (
    McpServerException,
    authorize_tool_call,
    bearer_challenge,
    json_rpc_error,
    protected_resource_router,
)
from app.mcp.server import NotesServer
from config.mcp import McpConfig


class McpServiceProvider(Provider):
    def boot(self) -> None:
        config: McpConfig = self.config
        scopes = list(self.app.make("auth_manager").oauth2_config.scopes)
        server = NotesServer()

        self.app.include_router(protected_resource_router(config, scopes))
        self.app.include_router(
            server.router(config.path),
            dependencies=[Depends(authorize_tool_call(server))],
        )

        challenge = bearer_challenge(config)
        for exception in (
            AuthenticationException,
            InvalidTokenException,
            MissingScopeException,
        ):
            self.app.add_exception_handler(exception, challenge)
        self.app.add_exception_handler(McpServerException, json_rpc_error)
        self.commands([CreateClientCommand])
