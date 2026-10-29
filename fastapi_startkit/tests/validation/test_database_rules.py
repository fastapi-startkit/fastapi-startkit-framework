import tempfile
from pathlib import Path
from typing import Annotated
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from fastapi_startkit.masoniteorm import DatabaseConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.facades.DB import DB
from fastapi_startkit.masoniteorm.models.model import Model
from fastapi_startkit.validation import Email, Field, FormRequest, ValidationException


class Account(Model):
    __table__ = "accounts"


class Signup(FormRequest):
    email: Annotated[str, Email().required().unique("accounts")]
    handle: Annotated[str, Field().required().unique(Account, "username")]


class UpdateAccount(FormRequest):
    email: Annotated[str, Field().required().unique("accounts", ignore=lambda data: data["account_id"])]


class UpdateByHandle(FormRequest):
    email: Annotated[str, Field().unique(Account, ignore="jane", ignore_column="username")]


class Transfer(FormRequest):
    account: Annotated[str, Field().required().exists("accounts", "username")]
    owner: Annotated[str | None, Field().exists(Account, "email").msg("Unknown owner :attribute.")] = None


class DatabaseRulesTest(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        url = f"sqlite+aiosqlite:///{Path(self.tmp.name) / 'validation.sqlite3'}"
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

        connection = self.manager.connection()
        await connection.statement(
            "CREATE TABLE accounts (id INTEGER PRIMARY KEY, email VARCHAR(255), username VARCHAR(255))"
        )
        await connection.insert("INSERT INTO accounts (id, email, username) VALUES (1, 'jane@example.com', 'jane')")

    async def asyncTearDown(self):
        await self.manager.clear()
        self.tmp.cleanup()

    async def assert_errors(self, request: FormRequest, errors: dict[str, list[str]], context=None):
        with self.assertRaises(ValidationException) as caught:
            await request.validate_async(context)
        self.assertEqual(caught.exception.errors, errors)

    async def test_unique_passes_for_new_values(self):
        request = Signup(email="john@example.com", handle="john")

        self.assertIs(await request.validate_async(), request)

    async def test_unique_fails_for_taken_values_by_table_and_model(self):
        await self.assert_errors(
            Signup(email="jane@example.com", handle="jane"),
            {"email": ["The email has already been taken."], "handle": ["The handle has already been taken."]},
        )

    async def test_unique_ignores_the_row_from_context(self):
        request = UpdateAccount(email="jane@example.com")

        self.assertIs(await request.validate_async({"account_id": 1}), request)
        await self.assert_errors(request, {"email": ["The email has already been taken."]}, {"account_id": 2})

    async def test_unique_ignore_value_and_column(self):
        self.assertIsNotNone(await UpdateByHandle(email="jane@example.com").validate_async())

    async def test_unique_skips_empty_values(self):
        self.assertIsNotNone(await UpdateByHandle(email="").validate_async())

    async def test_exists(self):
        self.assertIsNotNone(await Transfer(account="jane", owner="jane@example.com").validate_async())
        self.assertIsNotNone(await Transfer(account="jane").validate_async())
        await self.assert_errors(
            Transfer(account="john", owner="john@example.com"),
            {"account": ["The selected account is invalid."], "owner": ["Unknown owner owner."]},
        )
