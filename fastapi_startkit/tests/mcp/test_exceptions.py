import json
from typing import Annotated, Any

from pydantic import BaseModel

from fastapi_startkit.exceptions import ValidationException
from fastapi_startkit.mcp import JsonRpcError, McpExceptionHandler, Response, Server, Tool
from fastapi_startkit.mcp.protocol import Protocol
from fastapi_startkit.validation import Field, FormRequest, Validator


class Address(BaseModel):
    city: str


class Signup(FormRequest):
    username: Annotated[str, Field().required().string().min(3)]
    age: Annotated[int, Field().required().integer().between(18, 120)]
    address: Address | None = None

    @classmethod
    def prepare_for_validation(cls, validator: Validator) -> None:
        validator.merge({"username": str(validator.data.get("username", "")).strip()})


class SignupTool(Tool):
    name = "signup"
    description = "Sign a user up."

    def schema(self) -> type[Signup]:
        return Signup

    async def handle(self, arguments: dict[str, Any]) -> Response:
        return Response.text(json.dumps(arguments))


class EpisodeMissing(LookupError):
    pass


class EpisodeGone(EpisodeMissing):
    pass


EXCEPTIONS: dict[str, Exception] = {
    "runtime": RuntimeError("Upstream is down"),
    "validation": ValidationException({"title": ["The title field is required."]}),
    "gone": EpisodeGone("Episode 7"),
}


class RaisingTool(Tool):
    name = "raising"
    description = "Raises the exception named in its arguments."

    async def handle(self, arguments: dict[str, Any]) -> Response:
        raise EXCEPTIONS[arguments["kind"]]


class EpisodeMissingRenderer:
    async def render(self, request: Any, exc: EpisodeMissing) -> JsonRpcError:
        return JsonRpcError(-32004, f"{exc} was not found.")


class AppExceptionHandler(McpExceptionHandler):
    def register(self) -> None:
        super().register()
        self.register_handler(EpisodeMissing, EpisodeMissingRenderer())


class CallableExceptionHandler(McpExceptionHandler):
    def register(self) -> None:
        self.register_render(RuntimeError, lambda request, exc: JsonRpcError(-32001, "Try again later"))


class AppServer(Server):
    name = "app"

    def tools(self) -> list[type[Tool]]:
        return [SignupTool, RaisingTool]


class CustomServer(AppServer):
    exception_handler = AppExceptionHandler


class CallableServer(AppServer):
    exception_handler = CallableExceptionHandler


async def call(name: str, arguments: dict[str, Any], server: Server | None = None) -> dict[str, Any]:
    return await Protocol(server or AppServer()).dispatch("tools/call", {"name": name, "arguments": arguments}, 1)


class TestValidationExceptionRendering:
    async def test_validation_exception_is_a_server_error_with_field_messages(self):
        result = await call("raising", {"kind": "validation"})

        assert result["error"] == {
            "code": -32000,
            "message": "The title field is required.",
            "data": {"title": ["The title field is required."]},
        }

    async def test_unknown_exception_keeps_its_message_without_data(self):
        result = await call("raising", {"kind": "runtime"})

        assert result["error"] == {"code": -32000, "message": "Upstream is down"}

    async def test_exception_without_a_renderer_keeps_its_message(self):
        result = await call("raising", {"kind": "gone"})

        assert result["error"] == {"code": -32000, "message": "Episode 7"}


class TestCustomRenderers:
    async def test_server_renders_registered_exception_subclasses(self):
        result = await call("raising", {"kind": "gone"}, CustomServer())

        assert result["error"] == {"code": -32004, "message": "Episode 7 was not found."}

    async def test_custom_handler_keeps_validation_rendering(self):
        result = await call("raising", {"kind": "validation"}, CustomServer())

        assert result["error"]["data"] == {"title": ["The title field is required."]}

    async def test_render_callables_return_errors(self):
        result = await call("raising", {"kind": "runtime"}, CallableServer())

        assert result["error"] == {"code": -32001, "message": "Try again later"}


class TestFormRequestTools:
    async def test_invalid_arguments_render_every_field_message(self):
        result = await call("signup", {"username": "al", "age": 12})

        assert result["error"]["code"] == -32000
        assert result["error"]["message"].endswith("(and 1 more error)")
        assert set(result["error"]["data"]) == {"username", "age"}

    async def test_missing_arguments_are_required(self):
        result = await call("signup", {})

        assert result["error"]["data"]["username"] == ["The username field is required."]

    async def test_handle_receives_the_validated_arguments(self):
        result = await call("signup", {"username": "  alice ", "age": "30", "address": {"city": "Lyon"}})

        assert json.loads(result["result"]["content"][0]["text"]) == {
            "username": "alice",
            "age": 30,
            "address": {"city": "Lyon"},
        }

    async def test_nested_models_without_rules_are_validated(self):
        result = await call("signup", {"username": "alice", "age": 30, "address": {}})

        assert result["error"]["code"] == -32000
        assert result["error"]["data"] == {"address.city": ["Field required"]}
