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
