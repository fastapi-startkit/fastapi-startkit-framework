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


async def account_id(data):
    return data["account_id"]


class UpdateAccountAsync(FormRequest):
    email: Annotated[str, Field().required().unique("accounts", ignore=account_id)]


class StrictSignup(FormRequest):
    stop_on_first_failure = True

    email: Annotated[str, Email().required()]
    handle: Annotated[str, Field().required().unique("accounts", "username")]


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

    async def assert_errors(self, model: type[FormRequest], data: dict, errors: dict[str, list[str]], context=None):
        with self.assertRaises(ValidationException) as caught:
            await model.validate_input(data, context)
        self.assertEqual(caught.exception.errors, errors)

    async def test_unique_passes_for_new_values(self):
        request = await Signup.validate_input({"email": "john@example.com", "handle": "john"})

        self.assertEqual(request.handle, "john")

    async def test_unique_fails_for_taken_values_by_table_and_model(self):
        await self.assert_errors(
            Signup,
            {"email": "jane@example.com", "handle": "jane"},
            {"email": ["The email has already been taken."], "handle": ["The handle has already been taken."]},
        )

    async def test_database_rules_run_with_sync_rule_failures_in_one_pass(self):
        await self.assert_errors(
            Signup,
            {"email": "not-an-email", "handle": "jane"},
            {
                "email": ["The email field must be a valid email address."],
                "handle": ["The handle has already been taken."],
            },
        )

    async def test_unique_ignores_the_row_from_context(self):
        data = {"email": "jane@example.com"}

        self.assertEqual((await UpdateAccount.validate_input(data, {"account_id": 1})).email, "jane@example.com")
        await self.assert_errors(
            UpdateAccount, data, {"email": ["The email has already been taken."]}, {"account_id": 2}
        )

    async def test_unique_ignore_can_be_async(self):
        data = {"email": "jane@example.com"}

        self.assertIsNotNone(await UpdateAccountAsync.validate_input(data, {"account_id": 1}))
        await self.assert_errors(
            UpdateAccountAsync, data, {"email": ["The email has already been taken."]}, {"account_id": 2}
        )

    async def test_unique_ignore_value_and_column(self):
        self.assertIsNotNone(await UpdateByHandle.validate_input({"email": "jane@example.com"}))

    async def test_unique_skips_empty_values(self):
        self.assertIsNotNone(await UpdateByHandle.validate_input({"email": ""}))

    async def test_exists(self):
        self.assertIsNotNone(await Transfer.validate_input({"account": "jane", "owner": "jane@example.com"}))
        self.assertIsNotNone(await Transfer.validate_input({"account": "jane"}))
        await self.assert_errors(
            Transfer,
            {"account": "john", "owner": "john@example.com"},
            {"account": ["The selected account is invalid."], "owner": ["Unknown owner owner."]},
        )

    async def test_stop_on_first_failure_skips_later_database_rules(self):
        with patch.object(DB, "table", side_effect=AssertionError("queried")):
            await self.assert_errors(
                StrictSignup,
                {"email": "nope", "handle": "jane"},
                {"email": ["The email field must be a valid email address."]},
            )
