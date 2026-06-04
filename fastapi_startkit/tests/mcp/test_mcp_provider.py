"""Tests for McpProvider."""

from fastapi_startkit.mcp import McpProvider
from fastapi_startkit.providers import Provider


def test_mcp_provider_is_a_provider():
    assert issubclass(McpProvider, Provider)


def test_mcp_provider_key():
    assert McpProvider.provider_key == "mcp"


def test_register_is_callable():
    # Should not raise
    class FakeApp:
        pass

    provider = McpProvider(FakeApp())
    provider.register()


def test_boot_is_callable():
    class FakeApp:
        pass

    provider = McpProvider(FakeApp())
    provider.boot()
