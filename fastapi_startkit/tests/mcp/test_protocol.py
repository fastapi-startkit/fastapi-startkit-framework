"""Tests for the Protocol dispatcher — all 7 MCP methods."""

import pytest
from pydantic import BaseModel

from fastapi_startkit.mcp.protocol import Protocol, MCP_PROTOCOL_VERSION
from fastapi_startkit.mcp.server import Server
from fastapi_startkit.mcp.tool import Tool
from fastapi_startkit.mcp.prompt import Prompt
from fastapi_startkit.mcp.argument import Argument
from fastapi_startkit.mcp.resource import Resource
from fastapi_startkit.mcp.response import Response


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class EchoTool(Tool):
    name = "echo"
    description = "Echo the input."

    async def handle(self, arguments: dict) -> Response:
        return Response.text(arguments.get("msg", ""))


class AddInput(BaseModel):
    a: int
    b: int


class AddTool(Tool):
    name = "add"
    description = "Add two integers."

    def schema(self):
        return AddInput

    async def handle(self, arguments: dict) -> Response:
        return Response.text(str(arguments.get("a", 0) + arguments.get("b", 0)))


class GreetPrompt(Prompt):
    name = "greet"
    description = "Greeting prompt."

    def arguments(self):
        return [Argument(name="name", required=True)]

    async def handle(self, arguments: dict) -> Response:
        return Response.text(f"Hello, {arguments.get('name', 'there')}!")


class HiddenPrompt(Prompt):
    name = "hidden"

    def should_register(self) -> bool:
        return False

    async def handle(self, arguments: dict) -> Response:
        return Response.text("hidden")


class StatusResource(Resource):
    uri = "resource:///status"
    name = "status"

    async def read(self, **kwargs) -> str:
        return "running"


class FullServer(Server):
    name = "full-server"
    description = "Test server"
    instructions = "Use tools."

    def tools(self):
        return [EchoTool, AddTool]

    def prompts(self):
        return [GreetPrompt, HiddenPrompt]

    def resources(self):
        return [StatusResource]


class EmptyServer(Server):
    name = "empty-server"


@pytest.fixture
def protocol():
    return Protocol(FullServer())


@pytest.fixture
def empty_protocol():
    return Protocol(EmptyServer())


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------


class TestInitialize:
    async def test_returns_protocol_version(self, protocol):
        result = await protocol.dispatch("initialize", {}, 1)
        assert result["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION

    async def test_returns_server_info(self, protocol):
        result = await protocol.dispatch("initialize", {}, 1)
        assert result["result"]["serverInfo"]["name"] == "full-server"

    async def test_includes_description(self, protocol):
        result = await protocol.dispatch("initialize", {}, 1)
        assert result["result"]["description"] == "Test server"

    async def test_includes_instructions(self, protocol):
        result = await protocol.dispatch("initialize", {}, 1)
        assert result["result"]["instructions"] == "Use tools."

    async def test_capabilities_present(self, protocol):
        result = await protocol.dispatch("initialize", {}, 1)
        caps = result["result"]["capabilities"]
        assert "tools" in caps
        assert "prompts" in caps
        assert "resources" in caps

    async def test_response_has_id(self, protocol):
        result = await protocol.dispatch("initialize", {}, 99)
        assert result["id"] == 99


# ---------------------------------------------------------------------------
# tools/list
# ---------------------------------------------------------------------------


class TestToolsList:
    async def test_returns_tools_key(self, protocol):
        result = await protocol.dispatch("tools/list", {}, 1)
        assert "tools" in result["result"]

    async def test_lists_registered_tools(self, protocol):
        result = await protocol.dispatch("tools/list", {}, 1)
        names = [t["name"] for t in result["result"]["tools"]]
        assert "echo" in names
        assert "add" in names

    async def test_empty_server_returns_empty_list(self, empty_protocol):
        result = await empty_protocol.dispatch("tools/list", {}, 1)
        assert result["result"]["tools"] == []


# ---------------------------------------------------------------------------
# tools/call
# ---------------------------------------------------------------------------


class TestToolsCall:
    async def test_calls_echo_tool(self, protocol):
        result = await protocol.dispatch("tools/call", {"name": "echo", "arguments": {"msg": "hi"}}, 1)
        content = result["result"]["content"]
        assert content[0]["text"] == "hi"

    async def test_calls_add_tool(self, protocol):
        result = await protocol.dispatch("tools/call", {"name": "add", "arguments": {"a": 2, "b": 3}}, 1)
        content = result["result"]["content"]
        assert content[0]["text"] == "5"

    async def test_unknown_tool_returns_error(self, protocol):
        result = await protocol.dispatch("tools/call", {"name": "unknown"}, 1)
        assert "error" in result["result"]

    async def test_missing_arguments_uses_defaults(self, protocol):
        result = await protocol.dispatch("tools/call", {"name": "echo"}, 1)
        content = result["result"]["content"]
        assert content[0]["text"] == ""


# ---------------------------------------------------------------------------
# prompts/list
# ---------------------------------------------------------------------------


class TestPromptsList:
    async def test_returns_prompts_key(self, protocol):
        result = await protocol.dispatch("prompts/list", {}, 1)
        assert "prompts" in result["result"]

    async def test_lists_registered_prompts(self, protocol):
        result = await protocol.dispatch("prompts/list", {}, 1)
        names = [p["name"] for p in result["result"]["prompts"]]
        assert "greet" in names

    async def test_hidden_prompt_not_listed(self, protocol):
        result = await protocol.dispatch("prompts/list", {}, 1)
        names = [p["name"] for p in result["result"]["prompts"]]
        assert "hidden" not in names

    async def test_empty_server_returns_empty_list(self, empty_protocol):
        result = await empty_protocol.dispatch("prompts/list", {}, 1)
        assert result["result"]["prompts"] == []


# ---------------------------------------------------------------------------
# prompts/get
# ---------------------------------------------------------------------------


class TestPromptsGet:
    async def test_returns_messages_key(self, protocol):
        result = await protocol.dispatch("prompts/get", {"name": "greet", "arguments": {"name": "Alice"}}, 1)
        assert "messages" in result["result"]

    async def test_message_content_correct(self, protocol):
        result = await protocol.dispatch("prompts/get", {"name": "greet", "arguments": {"name": "Bob"}}, 1)
        text = result["result"]["messages"][0]["content"]["text"]
        assert "Bob" in text

    async def test_unknown_prompt_returns_error(self, protocol):
        result = await protocol.dispatch("prompts/get", {"name": "unknown"}, 1)
        assert "error" in result["result"]


# ---------------------------------------------------------------------------
# resources/list
# ---------------------------------------------------------------------------


class TestResourcesList:
    async def test_returns_resources_key(self, protocol):
        result = await protocol.dispatch("resources/list", {}, 1)
        assert "resources" in result["result"]

    async def test_lists_registered_resources(self, protocol):
        result = await protocol.dispatch("resources/list", {}, 1)
        uris = [r["uri"] for r in result["result"]["resources"]]
        assert "resource:///status" in uris

    async def test_empty_server_returns_empty_list(self, empty_protocol):
        result = await empty_protocol.dispatch("resources/list", {}, 1)
        assert result["result"]["resources"] == []


# ---------------------------------------------------------------------------
# resources/read
# ---------------------------------------------------------------------------


class TestResourcesRead:
    async def test_returns_contents_key(self, protocol):
        result = await protocol.dispatch("resources/read", {"uri": "resource:///status"}, 1)
        assert "contents" in result["result"]

    async def test_resource_text_content(self, protocol):
        result = await protocol.dispatch("resources/read", {"uri": "resource:///status"}, 1)
        assert result["result"]["contents"][0]["text"] == "running"

    async def test_resource_uri_in_contents(self, protocol):
        result = await protocol.dispatch("resources/read", {"uri": "resource:///status"}, 1)
        assert result["result"]["contents"][0]["uri"] == "resource:///status"

    async def test_unknown_resource_returns_error(self, protocol):
        result = await protocol.dispatch("resources/read", {"uri": "resource:///unknown"}, 1)
        assert "error" in result["result"]


# ---------------------------------------------------------------------------
# Unknown method
# ---------------------------------------------------------------------------


class TestUnknownMethod:
    async def test_unknown_method_returns_error(self, protocol):
        result = await protocol.dispatch("no/such/method", {}, 1)
        assert "error" in result
        assert result["error"]["code"] == -32601

    async def test_error_includes_method_name(self, protocol):
        result = await protocol.dispatch("invalid", {}, 1)
        assert "invalid" in result["error"]["message"]


# ---------------------------------------------------------------------------
# Notification (id is None)
# ---------------------------------------------------------------------------


class TestNotificationDispatch:
    async def test_notification_returns_result(self, protocol):
        # Protocol.dispatch still returns a dict even for notifications;
        # the 202 response is handled at the server level.
        result = await protocol.dispatch("tools/list", {}, None)
        assert "result" in result

    async def test_notification_id_is_none_in_response(self, protocol):
        result = await protocol.dispatch("tools/list", {}, None)
        assert result["id"] is None
