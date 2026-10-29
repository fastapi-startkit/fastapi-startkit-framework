import tempfile
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm.facades.DB import DB as DBFacade
from fastapi_startkit.masoniteorm.models.model import Model
from fastapi_startkit.validation import Email, FormRequest, Validated

from .fixtures.db import DB


class UpdateMember(FormRequest):
    email: Annotated[str, Email().required().unique("validation_members", ignore=lambda data: data["member_id"])]


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, env="testing", providers=[FastAPIProvider])

    @app.fastapi.put("/members/{member_id}")
    async def update(member_id: int, data: Validated[UpdateMember]):
        return {"id": member_id, "email": data.email}

    return app


class ValidatedUniquePostgresTest(HttpTestCase):
    def get_application(self) -> Application:
        if not hasattr(self, "_application"):
            self._tmp_dir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmp_dir.cleanup)
            original_instance = Container._instance
            self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
            self._application = make_application(Path(self._tmp_dir.name))
        return self._application

    async def asyncSetUp(self):
        await super().asyncSetUp()
        original_manager = Model.db_manager
        Model.db_manager = DB
        self.addCleanup(setattr, Model, "db_manager", original_manager)
        db_patch = patch.object(DBFacade, "_instance", DB)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        await DB.clear()
        connection = DB.connection()
        await connection.statement("DROP TABLE IF EXISTS validation_members")
        await connection.statement("CREATE TABLE validation_members (id INTEGER PRIMARY KEY, email VARCHAR(255))")
        await connection.insert("INSERT INTO validation_members (id, email) VALUES (1, 'jane@example.com')")

    async def asyncTearDown(self):
        await DB.connection().statement("DROP TABLE IF EXISTS validation_members")
        await DB.clear()
        await super().asyncTearDown()

    async def test_unique_ignore_uses_the_typed_path_parameter(self):
        own = await self.put("/members/1", json={"email": "jane@example.com"})
        other = await self.put("/members/2", json={"email": "jane@example.com"})

        own.assert_status(200)
        self.assertEqual(own.json(), {"id": 1, "email": "jane@example.com"})
        other.assert_status(422)
        self.assertEqual(other.json()["errors"], {"email": ["The email has already been taken."]})

    async def test_invalid_path_parameter_returns_the_path_error(self):
        response = await self.put("/members/abc", json={"email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), ["member_id"])
