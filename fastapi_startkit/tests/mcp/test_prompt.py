"""Tests for the Prompt base class."""

from fastapi_startkit.mcp.prompt import Prompt
from fastapi_startkit.mcp.argument import Argument
from fastapi_startkit.mcp.response import Response


# ---------------------------------------------------------------------------
# Concrete prompt implementations
# ---------------------------------------------------------------------------


class GreetPrompt(Prompt):
    name = "greet"
    description = "Generates a personalised greeting."
    title = "Greeting"

    def arguments(self) -> list[Argument]:
        return [
            Argument(name="name", description="The person to greet", required=True),
        ]

    async def handle(self, arguments: dict) -> Response:
        name = arguments.get("name", "there")
        return Response.text(f"Hello, {name}!")


class SimplePrompt(Prompt):
    name = "simple"

    async def handle(self, arguments: dict) -> Response:
        return Response.text("simple")


class DisabledPrompt(Prompt):
    name = "disabled"

    def should_register(self) -> bool:
        return False

    async def handle(self, arguments: dict) -> Response:
        return Response.text("disabled")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPromptToJson:
    def test_name_serialised(self):
        assert GreetPrompt().to_json()["name"] == "greet"

    def test_description_serialised(self):
        assert GreetPrompt().to_json()["description"] == "Generates a personalised greeting."

    def test_title_serialised(self):
        assert GreetPrompt().to_json()["title"] == "Greeting"

    def test_arguments_serialised(self):
        data = GreetPrompt().to_json()
        assert "arguments" in data
        assert data["arguments"][0]["name"] == "name"

    def test_description_omitted_when_none(self):
        data = SimplePrompt().to_json()
        assert "description" not in data

    def test_arguments_omitted_when_empty(self):
        data = SimplePrompt().to_json()
        assert "arguments" not in data


class TestShouldRegister:
    def test_defaults_to_true(self):
        assert GreetPrompt().should_register() is True

    def test_returns_false_when_overridden(self):
        assert DisabledPrompt().should_register() is False


class TestPromptArguments:
    def test_returns_argument_instances(self):
        args = GreetPrompt().arguments()
        assert isinstance(args[0], Argument)

    def test_default_returns_empty_list(self):
        assert SimplePrompt().arguments() == []


class TestPromptHandle:
    async def test_handle_returns_response(self):
        result = await GreetPrompt().handle({"name": "Alice"})
        assert result.to_content()[0]["text"] == "Hello, Alice!"

    async def test_handle_default_name(self):
        result = await GreetPrompt().handle({})
        assert "there" in result.to_content()[0]["text"]
