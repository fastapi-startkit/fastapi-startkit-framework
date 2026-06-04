"""Tests for McpProvider (task #39)."""

import pytest
from fastapi.testclient import TestClient

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.mcp import McpProvider, Server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container_instance():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def tmp_app(tmp_path):
    """A bare Application with no extra providers."""
    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# Stub servers
# ---------------------------------------------------------------------------


class MinimalServer(Server):
    name = "minimal"


class EchoServer(Server):
    name = "echo"


# ---------------------------------------------------------------------------
# Stub providers
# ---------------------------------------------------------------------------


class MinimalMcpProvider(McpProvider):
    def server(self) -> Server:
        return MinimalServer()


class CustomPrefixProvider(McpProvider):
    prefix = "/api/mcp"

    def server(self) -> Server:
        return MinimalServer()


# ---------------------------------------------------------------------------
# Test: server() not overridden raises NotImplementedError
# ---------------------------------------------------------------------------


class TestServerNotOverridden:
    def test_raises_not_implemented(self, tmp_app):
        provider = McpProvider(tmp_app)
        with pytest.raises(NotImplementedError, match="Subclasses must implement server()"):
            provider.server()


# ---------------------------------------------------------------------------
# Test: register() binds the server into the container
# ---------------------------------------------------------------------------


class TestRegisterPhase:
    def test_register_binds_server(self, tmp_path):
        app = Application(base_path=tmp_path, env="testing", providers=[MinimalMcpProvider])
        server = app.make("mcp.server")
        assert isinstance(server, MinimalServer)

    def test_register_binds_correct_instance(self, tmp_path):
        class SpecificServer(Server):
            name = "specific"

        class SpecificProvider(McpProvider):
            def server(self) -> Server:
                return SpecificServer()

        app = Application(base_path=tmp_path, env="testing", providers=[SpecificProvider])
        server = app.make("mcp.server")
        assert isinstance(server, SpecificServer)
        assert server.name == "specific"


# ---------------------------------------------------------------------------
# Test: boot() mounts the router at the default /mcp prefix
# ---------------------------------------------------------------------------


class TestBootMountsRouter:
    def _make_test_client(self, provider_class) -> TestClient:
        """Build a TestClient from an Application with the given MCP provider."""
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp())
        app = Application(base_path=tmp, env="testing", providers=[provider_class])
        return TestClient(app.fastapi)

    def test_post_to_mcp_returns_json_rpc_response(self):
        client = self._make_test_client(MinimalMcpProvider)
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            "id": 1,
        }
        response = client.post("/mcp", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        assert "result" in body
        assert body["result"]["protocolVersion"] == "2024-11-05"

    def test_post_to_mcp_returns_server_info(self):
        client = self._make_test_client(MinimalMcpProvider)
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            "id": 2,
        }
        response = client.post("/mcp", json=payload)
        body = response.json()
        assert body["result"]["serverInfo"]["name"] == "minimal"

    def test_get_to_mcp_returns_405(self):
        client = self._make_test_client(MinimalMcpProvider)
        response = client.get("/mcp")
        assert response.status_code == 405

    def test_tools_list_returns_empty_when_no_tools(self):
        client = self._make_test_client(MinimalMcpProvider)
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "params": {},
            "id": 3,
        }
        response = client.post("/mcp", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["result"]["tools"] == []


# ---------------------------------------------------------------------------
# Test: custom prefix
# ---------------------------------------------------------------------------


class TestCustomPrefix:
    def _make_test_client(self, provider_class) -> TestClient:
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp())
        app = Application(base_path=tmp, env="testing", providers=[provider_class])
        return TestClient(app.fastapi)

    def test_custom_prefix_mounts_at_correct_path(self):
        client = self._make_test_client(CustomPrefixProvider)
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            "id": 1,
        }
        response = client.post("/api/mcp", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert "result" in body

    def test_default_prefix_not_available_with_custom_prefix(self):
        client = self._make_test_client(CustomPrefixProvider)
        payload = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
            "id": 1,
        }
        response = client.post("/mcp", json=payload)
        assert response.status_code == 404

    def test_prefix_attribute_is_customisable(self):
        assert CustomPrefixProvider.prefix == "/api/mcp"

    def test_default_prefix_is_mcp(self):
        assert McpProvider.prefix == "/mcp"
