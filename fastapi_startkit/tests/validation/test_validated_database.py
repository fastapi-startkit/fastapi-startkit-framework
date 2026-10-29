import tempfile
from pathlib import Path
from typing import Annotated
from unittest.mock import patch

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm import DatabaseConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.facades.DB import DB
from fastapi_startkit.masoniteorm.models.model import Model
from fastapi_startkit.validation import Email, FormRequest, Validated


class UpdateAccount(FormRequest):
    email: Annotated[str, Email().required().unique("accounts", ignore=lambda data: data["account_id"])]


def make_application(base_path: Path) -> Application:
    app = Application(base_path=base_path, providers=[FastAPIProvider])

    @app.fastapi.put("/accounts/{account_id}")
    async def update(account_id: int, data: Validated[UpdateAccount]):
        return {"id": account_id, "email": data.email}

    return app


class ValidatedUniqueTest(HttpTestCase):
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
        url = f"sqlite+aiosqlite:///{Path(self._tmp_dir.name) / 'validated.sqlite3'}"
        self.manager = DatabaseManager(
            ConnectionFactory(),
            DatabaseConfig(default="sqlite", connections={"sqlite": SQLiteConfig(driver="sqlite", url=url)}),
        )
        original_manager = Model.db_manager
        Model.db_manager = self.manager
        self.addCleanup(setattr, Model, "db_manager", original_manager)
        db_patch = patch.object(DB, "_instance", self.manager)
        db_patch.start()
        self.addCleanup(db_patch.stop)

        self.connection = self.manager.connection()
        await self.connection.statement("CREATE TABLE accounts (id INTEGER PRIMARY KEY, email VARCHAR(255))")
        await self.connection.insert("INSERT INTO accounts (id, email) VALUES (1, 'jane@example.com')")

    async def asyncTearDown(self):
        await self.manager.clear()
        await super().asyncTearDown()

    async def test_unique_ignore_receives_the_typed_path_parameter(self):
        select_one = type(self.connection).select_one
        with patch.object(type(self.connection), "select_one", autospec=True, side_effect=select_one) as spy:
            own = await self.put("/accounts/1", json={"email": "jane@example.com"})
            other = await self.put("/accounts/2", json={"email": "jane@example.com"})

        own.assert_status(200)
        other.assert_status(422)
        self.assertEqual(other.json()["errors"], {"email": ["The email has already been taken."]})
        self.assertEqual(
            [call.args[2] for call in spy.call_args_list], [["jane@example.com", 1], ["jane@example.com", 2]]
        )
        self.assertEqual([type(call.args[2][1]) for call in spy.call_args_list], [int, int])

    async def test_invalid_path_parameter_never_reaches_the_database(self):
        select_one = type(self.connection).select_one
        with patch.object(type(self.connection), "select_one", autospec=True, side_effect=select_one) as spy:
            response = await self.put("/accounts/abc", json={"email": "jane@example.com"})

        response.assert_status(422)
        self.assertEqual(list(response.json()["errors"]), ["account_id"])
        spy.assert_not_called()
