from fastapi_startkit.support import Provider


class McpProvider(Provider):
    """Provider that bootstraps the MCP component for fastapi-startkit.

    Register it alongside ``FastAPIProvider`` to make MCP available in
    your application::

        app = Application(providers=[FastAPIProvider, McpProvider])
    """

    provider_key = "mcp"

    def register(self) -> None:
        """Register MCP bindings into the container."""

    def boot(self) -> None:
        """Boot the MCP component."""
