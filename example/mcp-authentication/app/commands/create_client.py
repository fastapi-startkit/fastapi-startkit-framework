import asyncio

from cleo.helpers import option
from fastapi_startkit.console import Command


class CreateClientCommand(Command):
    name = "mcp:client"
    description = "Create a confidential client that can request MCP access tokens."
    options = [
        option("name", description="Client name.", flag=False, default="MCP client"),
        option("scopes", description="Space-separated scopes the client may request.", flag=False, default="notes:read notes:write"),
    ]

    def handle(self) -> int:
        client, secret = asyncio.run(self.register())
        self.line(f"Client ID: {client.id}")
        self.line(f"Client secret: {secret}")
        return 0

    async def register(self):
        manager = self.container.make("auth_manager")
        return await manager.client_repository.register(
            name=self.option("name"),
            redirect_uris=[],
            confidential=True,
            grant_types=["client_credentials"],
            scopes=self.option("scopes").split(),
        )
