from fastapi import Depends
from fastapi_startkit.support import Provider
from fastapi_startkit_auth import InsufficientScope, InvalidToken

from app.commands.create_client import CreateClientCommand
from app.mcp.auth import authorize_tool_call, bearer_challenge, protected_resource_router
from app.mcp.server import NotesServer
from config.mcp import McpConfig


class McpServiceProvider(Provider):
    def boot(self) -> None:
        config: McpConfig = self.config
        server = NotesServer()

        self.app.include_router(protected_resource_router(config))
        self.app.include_router(server.router(config.path), dependencies=[Depends(authorize_tool_call(server))])
        self.app.add_exception_handler(InvalidToken, bearer_challenge(config))
        self.app.add_exception_handler(InsufficientScope, bearer_challenge(config))
        self.commands([CreateClientCommand])
