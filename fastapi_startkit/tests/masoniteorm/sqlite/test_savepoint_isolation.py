import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.testing.transaction import DatabaseTransaction

from ..fixtures.model import User
from .test_case import TestCase

EMAIL = "savepoint@example.com"


async def create_user() -> None:
    await User.create({"email": EMAIL, "name": "Savepoint", "is_admin": False})


async def remaining_users() -> int:
    return await User.where("email", EMAIL).count()


class TestSQLiteSavepointIsolation(TestCase):
    async def test_outer_statement_first_rolls_back_savepoint(self):
        connection = self.db.connection(None)
        outer = connection.transaction()
        await outer.__aenter__()
        await connection.select("SELECT 1")
        async with connection.transaction():
            await create_user()
        await outer.rollback()
        await outer.__aexit__(None, None, None)

        assert await remaining_users() == 0

    async def test_savepoint_first_rolls_back_with_outer_transaction(self):
        connection = self.db.connection(None)
        outer = connection.transaction()
        await outer.__aenter__()
        async with connection.transaction():
            await create_user()
        await outer.rollback()
        await outer.__aexit__(None, None, None)

        assert await remaining_users() == 0

    async def test_database_transaction_isolates_app_transaction(self):
        harness = DatabaseTransaction()
        await harness.asyncStartTestRun()
        try:
            async with self.db.connection(None).transaction():
                await create_user()
            assert await remaining_users() == 1
        finally:
            await harness.asyncStopTestRun()

        assert await remaining_users() == 0

    async def test_rolled_back_savepoint_keeps_outer_writes(self):
        connection = self.db.connection(None)
        async with connection.transaction():
            await create_user()
            savepoint = connection.transaction()
            await savepoint.__aenter__()
            await User.create({"email": "inner@example.com", "name": "Inner", "is_admin": False})
            await savepoint.rollback()
            await savepoint.__aexit__(None, None, None)

        assert await remaining_users() == 1
        assert await User.where("email", "inner@example.com").count() == 0


class TestSQLiteSavepointConcurrency(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.sqlite = SQliteConnection(self.engine, SQLiteConfig(database=":memory:"))
        await self.sqlite.statement("CREATE TABLE items (name VARCHAR(50))")

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def insert_nested(self, name: str) -> None:
        async with self.sqlite.transaction():
            async with self.sqlite.transaction():
                await self.sqlite.insert("INSERT INTO items (name) VALUES (?)", [name])

    async def insert_plain(self, name: str) -> None:
        async with self.sqlite.transaction():
            await self.sqlite.insert("INSERT INTO items (name) VALUES (?)", [name])

    async def count(self) -> int:
        row = await self.sqlite.select_one("SELECT COUNT(*) AS total FROM items")
        assert row is not None
        return row["total"]

    async def test_concurrent_nested_transactions_on_shared_connection(self):
        results = await asyncio.gather(
            *(self.insert_nested(f"nested-{index}") for index in range(5)), return_exceptions=True
        )

        assert [result for result in results if isinstance(result, BaseException)] == []
        assert await self.count() == 5

    async def test_nested_transaction_racing_plain_transaction_never_collides_on_begin(self):
        for first, second in ((self.insert_nested, self.insert_plain), (self.insert_plain, self.insert_nested)):
            results = await asyncio.gather(first("first"), second("second"), return_exceptions=True)

            assert not any("cannot start a transaction" in str(result) for result in results)

    def test_begin_failure_outside_a_transaction_is_raised(self):
        connection = MagicMock()
        connection.connection.driver_connection.in_transaction = False
        connection.exec_driver_sql.side_effect = OperationalError("BEGIN", {}, Exception("disk I/O error"))

        with pytest.raises(OperationalError):
            SQliteConnection.on_savepoint(connection, "sa_savepoint_1")
