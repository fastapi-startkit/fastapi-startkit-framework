import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends
from starlette.requests import Request as StarletteRequest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.validation import AsyncRule, Email, Field, FormRequest, Validated
from fastapi_startkit.validation.form_request import typed_path_params

TAKEN = {"jane@example.com": 1}
LOOKUPS: list[Any] = []


class UniqueEmail(AsyncRule):
    message = "The :attribute has already been taken."

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        LOOKUPS.append(data.get("user_id"))
        owner = TAKEN.get(value)
        return owner is None or owner == data.get("user_id")


class RegisterUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]
    username: Annotated[str, Field().required().string().min(3).max(10)]
    password: Annotated[str, Field().required().password()]
    password_confirmation: Annotated[str, Field().required().same_as("password")]


class UpdateUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]


class Request(FormRequest):
    email: Annotated[str, Email().required()]


TEAM_CONTEXT: list[dict[str, Any]] = []


class TeamMember(FormRequest):
    email: Annotated[str, Email().required()]

    async def validate_async(self, context: Mapping[str, Any] | None = None):
        TEAM_CONTEXT.append(dict(context or {}))
        return await super().validate_async(context)


async def tenant(tenant_id: int) -> int:
    return tenant_id


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, env="testing", providers=[FastAPIProvider])
    teams = APIRouter(prefix="/tenants/{tenant_id}/teams/{team_id}", dependencies=[Depends(tenant)])

    @teams.post("/members")
    async def add_member(team_id: int, data: Validated[TeamMember]):
        return {"email": data.email}

    app.fastapi.include_router(teams)

    @app.fastapi.post("/requests")
    async def request_model(data: Validated[Request]):
        return {"email": data.email}

    @app.fastapi.post("/register")
    async def register(data: Validated[RegisterUser]):
        return {"username": data.username}

    @app.fastapi.put("/users/{user_id}")
    async def update(user_id: int, data: Validated[UpdateUser]):
        return {"id": user_id, "email": data.email}

    @app.fastapi.post("/users/{user_id}/notes")
    async def note(user_id: int, data: Validated[UpdateUser], note: Annotated[str, Body()]):
        return {"id": user_id, "email": data.email, "note": note}

    @app.fastapi.post("/plain")
    async def plain(data: RegisterUser):
        return {"username": data.username}

    return app


VALID = {
    "email": "john@example.com",
    "username": "john",
    "password": "secret123",
    "password_confirmation": "secret123",
}


class FastAPIValidationTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            self._application = make_application(Path(self._tmp_dir.name))
        return self._application

    async def test_valid_request_reaches_the_endpoint(self):
        response = await self.post("/register", json=VALID)

        response.assert_status(200)
        self.assertEqual(response.json(), {"username": "john"})

    async def test_sync_rule_failures_return_laravel_shape(self):
        response = await self.post("/register", json={"email": "nope", "username": "jo", "password": "secret123"})

        response.assert_status(422)
        self.assertEqual(
            response.json(),
            {
                "message": "The email field must be a valid email address. (and 2 more errors)",
                "errors": {
                    "email": ["The email field must be a valid email address."],
                    "username": ["The username field must be at least 3 characters."],
                    "password_confirmation": ["The password confirmation field is required."],
                },
            },
        )

    async def test_async_rule_failures_return_laravel_shape(self):
        response = await self.post("/register", json={**VALID, "email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(
            response.json(),
            {
                "message": "The email has already been taken.",
                "errors": {"email": ["The email has already been taken."]},
            },
        )

    async def test_path_parameters_are_validation_context(self):
        own = await self.put("/users/1", json={"email": "jane@example.com"})
        other = await self.put("/users/2", json={"email": "jane@example.com"})

        own.assert_status(200)
        self.assertEqual(own.json(), {"id": 1, "email": "jane@example.com"})
        other.assert_status(422)
        self.assertEqual(other.json()["errors"], {"email": ["The email has already been taken."]})

    async def test_invalid_path_parameter_is_reported_before_async_rules(self):
        LOOKUPS.clear()

        response = await self.put("/users/abc", json={"email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), ["user_id"])
        self.assertEqual(LOOKUPS, [])

    async def test_validated_body_is_embedded_under_the_model_name_with_other_body_params(self):
        valid = await self.post("/users/1/notes", json={"update_user": {"email": "jane@example.com"}, "note": "hi"})
        taken = await self.post("/users/2/notes", json={"update_user": {"email": "jane@example.com"}, "note": "hi"})
        schema = (await self.get("/openapi.json")).json()
        body = schema["components"]["schemas"]["Body_note_users__user_id__notes_post"]

        valid.assert_status(200)
        self.assertEqual(valid.json(), {"id": 1, "email": "jane@example.com", "note": "hi"})
        taken.assert_status(422)
        self.assertEqual(taken.json()["errors"], {"email": ["The email has already been taken."]})
        self.assertEqual(sorted(body["properties"]), ["note", "update_user"])

    async def test_plain_body_parameter_runs_only_sync_rules(self):
        accepted = await self.post("/plain", json={**VALID, "email": "jane@example.com"})
        rejected = await self.post("/plain", json={**VALID, "username": "jo"})

        accepted.assert_status(200)
        rejected.assert_status(422)
        self.assertEqual(rejected.json()["errors"], {"username": ["The username field must be at least 3 characters."]})

    async def test_openapi_keeps_the_request_body_schema(self):
        schema = (await self.get("/openapi.json")).json()
        body = schema["paths"]["/register"]["post"]["requestBody"]["content"]["application/json"]["schema"]

        self.assertEqual(body, {"$ref": "#/components/schemas/RegisterUser"})

    async def test_router_prefix_and_dependency_path_params_are_typed_context(self):
        TEAM_CONTEXT.clear()

        valid = await self.post("/tenants/7/teams/3/members", json={"email": "a@example.com"})
        invalid = await self.post("/tenants/x/teams/3/members", json={"email": "a@example.com"})

        valid.assert_status(200)
        invalid.assert_status(422)
        self.assertEqual(TEAM_CONTEXT, [{"tenant_id": 7, "team_id": 3}])

    async def test_form_request_named_request_does_not_collide_with_the_http_request(self):
        response = await self.post("/requests", json={"email": "a@example.com"})

        response.assert_status(200)
        self.assertEqual(response.json(), {"email": "a@example.com"})


def test_path_params_without_a_matched_route_stay_raw():
    request = StarletteRequest({"type": "http", "path_params": {"user_id": "1"}})

    assert typed_path_params(request) == {"user_id": "1"}
