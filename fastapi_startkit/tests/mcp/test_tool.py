"""Tests for the Tool base class."""

from datetime import date
from enum import Enum
from typing import Annotated, Any

import pytest
from pydantic import BaseModel

from fastapi_startkit.exceptions import AuthorizationException, ValidationException
from fastapi_startkit.mcp.protocol import Protocol
from fastapi_startkit.mcp.server import Server
from fastapi_startkit.mcp.tool import Tool
from fastapi_startkit.mcp.response import Response
from fastapi_startkit.validation import Field, FormRequest, Validator


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


class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Episode(FormRequest):
    title: Annotated[str, Field().required().string().min(3)]
    status: Status = Status.DRAFT
    airs_on: date | None = None
    playlist_id: Annotated[int | None, Field().nullable().integer()] = None

    @classmethod
    def prepare_for_validation(cls, validator: Validator) -> None:
        validator.merge({"title": str(validator.data.get("title", "")).strip()})

    def playlist_attributes(self) -> dict[str, Any]:
        return {"playlist_id": self.playlist_id} if "playlist_id" in self.model_fields_set else {}


class EpisodeTool(Tool):
    name = "episodes"
    description = "Store an episode."
    received: Episode | None = None
    allowed = True

    def schema(self) -> type[Episode]:
        return Episode

    def authorize(self) -> bool:
        return self.allowed

    async def handle(self, arguments: Episode) -> Response:
        EpisodeTool.received = arguments
        return Response.text(arguments.title)


@pytest.fixture
def episode_tool():
    EpisodeTool.received = None
    EpisodeTool.allowed = True
    yield EpisodeTool()
    EpisodeTool.received = None
    EpisodeTool.allowed = True


class TestFormRequestToolHandle:
    async def test_handle_receives_the_validated_instance(self, episode_tool):
        result = await episode_tool.call({"title": "  Hello  ", "status": "published"})

        request = EpisodeTool.received
        assert isinstance(request, Episode)
        assert isinstance(request.status, Status)
        assert request.status is Status.PUBLISHED
        assert request.title == "Hello"
        assert "playlist_id" not in request.model_fields_set
        assert result.to_content()[0]["text"] == "Hello"

    async def test_an_omitted_enum_is_its_default_member(self, episode_tool):
        await episode_tool.call({"title": "Hello"})

        assert EpisodeTool.received.status is Status.DRAFT
        assert EpisodeTool.received.model_fields_set == {"title"}
        assert EpisodeTool.received.playlist_attributes() == {}

    async def test_a_value_outside_the_enum_is_a_validation_error(self, episode_tool):
        with pytest.raises(ValidationException) as raised:
            await episode_tool.call({"title": "Hello", "status": "bogus"})

        assert list(raised.value.bag.messages) == ["status"]
        assert EpisodeTool.received is None

    async def test_a_value_outside_the_enum_answers_with_the_status_errors(self, episode_tool):
        class EpisodeServer(Server):
            name = "episodes"

            def tools(self) -> list[type[Tool]]:
                return [EpisodeTool]

        arguments = {"title": "Hello", "status": "bogus"}
        result = await Protocol(EpisodeServer()).dispatch("tools/call", {"name": "episodes", "arguments": arguments}, 1)

        assert result["error"]["code"] == -32000
        assert list(result["error"]["data"]) == ["status"]
        assert EpisodeTool.received is None

    async def test_a_date_is_a_date(self, episode_tool):
        await episode_tool.call({"title": "Hello", "airs_on": "2026-11-10"})

        assert EpisodeTool.received.airs_on == date(2026, 11, 10)
        assert type(EpisodeTool.received.airs_on) is date

    async def test_a_field_sent_as_null_is_in_the_fields_set(self, episode_tool):
        await episode_tool.call({"title": "Hello", "playlist_id": None})

        assert "playlist_id" in EpisodeTool.received.model_fields_set
        assert EpisodeTool.received.playlist_attributes() == {"playlist_id": None}

    async def test_validate_input_returns_typed_values(self):
        request = await Episode.validate_input({"title": "Hello", "status": "published", "airs_on": "2026-11-10"})

        assert request.status is Status.PUBLISHED
        assert type(request.airs_on) is date

    async def test_a_refused_tool_never_validates_or_handles(self, episode_tool):
        EpisodeTool.allowed = False

        with pytest.raises(AuthorizationException):
            await episode_tool.call({})

        assert EpisodeTool.received is None

    async def test_tools_without_a_form_request_receive_the_arguments(self):
        result = await EchoTool().call({"message": "hello", "extra": 1})

        assert result.to_content()[0]["text"] == "hello"
