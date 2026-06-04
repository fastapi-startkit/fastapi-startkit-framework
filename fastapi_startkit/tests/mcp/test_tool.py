"""Tests for the Tool base class."""

import pytest
from pydantic import BaseModel

from fastapi_startkit.mcp.tool import Tool
from fastapi_startkit.mcp.response import Response


# ---------------------------------------------------------------------------
# Concrete tool implementations
# ---------------------------------------------------------------------------


class EchoTool(Tool):
    name = "echo"
    description = "Echo the input back."

    async def handle(self, arguments: dict) -> Response:
        return Response.text(arguments.get("message", ""))


class AddInput(BaseModel):
    a: int
    b: int


class AddOutput(BaseModel):
    total: int


class AddTool(Tool):
    name = "add"
    description = "Add two integers."

    def schema(self) -> type[BaseModel]:
        return AddInput

    def output_schema(self) -> type[BaseModel]:
        return AddOutput

    async def handle(self, arguments: dict) -> Response:
        total = arguments.get("a", 0) + arguments.get("b", 0)
        return Response.structure({"total": total})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolToJson:
    def test_name_is_serialised(self):
        assert EchoTool().to_json()["name"] == "echo"

    def test_description_is_serialised(self):
        assert EchoTool().to_json()["description"] == "Echo the input back."

    def test_input_schema_present_without_schema(self):
        data = EchoTool().to_json()
        assert "inputSchema" in data

    def test_input_schema_is_empty_object_when_no_schema(self):
        data = EchoTool().to_json()
        assert data["inputSchema"] == {"type": "object", "properties": {}}

    def test_input_schema_from_pydantic_model(self):
        data = AddTool().to_json()
        props = data["inputSchema"]["properties"]
        assert "a" in props
        assert "b" in props

    def test_output_schema_included_when_set(self):
        data = AddTool().to_json()
        assert "outputSchema" in data

    def test_output_schema_not_included_when_none(self):
        data = EchoTool().to_json()
        assert "outputSchema" not in data


class TestToolHandle:
    async def test_echo_handle(self):
        tool = EchoTool()
        result = await tool.handle({"message": "hello"})
        assert result.to_content()[0]["text"] == "hello"

    async def test_add_handle(self):
        import json
        tool = AddTool()
        result = await tool.handle({"a": 3, "b": 4})
        content = result.to_content()[0]
        assert json.loads(content["resource"]["text"]) == {"total": 7}

    async def test_schema_returns_pydantic_model(self):
        assert AddTool().schema() is AddInput

    async def test_no_schema_returns_none(self):
        assert EchoTool().schema() is None
