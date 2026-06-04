from fastapi_startkit.providers import Provider
from fastapi_startkit.mcp.server import Server


class McpProvider(Provider):
    """Base provider for mounting an MCP server on the FastAPI application.

    Subclass this provider, override ``server()`` to return your ``Server``
    instance, and register it alongside ``FastAPIProvider``::

        class AppMcpProvider(McpProvider):
            def server(self) -> Server:
                return DevToolsServer()

        app = Application(providers=[FastAPIProvider, AppMcpProvider])

    The router is mounted at ``/mcp`` by default. Override ``prefix`` to
    change it.
    """

    prefix: str = "/mcp"

    def server(self) -> Server:
        """Return the Server instance to mount. Must be overridden."""
        raise NotImplementedError("Subclasses must implement server()")

    def register(self) -> None:
        """Bind the MCP server instance into the container."""
        self.app.bind("mcp.server", self.server())

    def boot(self) -> None:
        """Mount the MCP router on the FastAPI application."""
        server = self.app.make("mcp.server")
        self.app.include_router(server.router(prefix=self.prefix))
