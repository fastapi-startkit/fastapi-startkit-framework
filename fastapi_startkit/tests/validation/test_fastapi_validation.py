import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated, Any

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.validation import AsyncRule, Email, Field, FormRequest, Validated

TAKEN = {"jane@example.com": 1}


class UniqueEmail(AsyncRule):
    message = "The :attribute has already been taken."

    async def passes(self, attribute: str, value: Any, data: Mapping[str, Any]) -> bool:
        owner = TAKEN.get(value)
        return owner is None or str(owner) == str(data.get("user_id"))


class RegisterUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]
    username: Annotated[str, Field().required().string().min(3).max(10)]
    password: Annotated[str, Field().required().password()]
    password_confirmation: Annotated[str, Field().required().same_as("password")]


class UpdateUser(FormRequest):
    email: Annotated[str, Email().required().add(UniqueEmail())]


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, env="testing", providers=[FastAPIProvider])

    @app.fastapi.post("/register")
    async def register(data: Validated[RegisterUser]):
        return {"username": data.username}

    @app.fastapi.put("/users/{user_id}")
    async def update(user_id: int, data: Validated[UpdateUser]):
        return {"id": user_id, "email": data.email}

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
