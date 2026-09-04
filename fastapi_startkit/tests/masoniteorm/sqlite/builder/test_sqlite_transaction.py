import asyncio
from contextvars import Context
from tempfile import NamedTemporaryFile

from sqlalchemy.ext.asyncio import create_async_engine

from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from ...fixtures.model import User
from ..fixtures.db import DB
from ..test_case import TestCase


class TestQueryBuilderTransaction(TestCase):
    async def test_concurrent_tasks_own_their_connections_and_transactions(self):
        conn = DB.connection("sqlite")
        ready = asyncio.Event()
        connection_ids = []

        async def transaction_query():
            await conn.begin_transaction()
            connection_ids.append(id(await conn.get_connection()))
            if len(connection_ids) == 2:
                ready.set()
            await ready.wait()
            self.assertGreater(await User.query().count(), 0)
            await conn.rollback()

        await asyncio.gather(transaction_query(), transaction_query())

        self.assertEqual(len(set(connection_ids)), 2)

    async def test_transaction_context_returns_connection_when_cancelled(self):
        with NamedTemporaryFile(suffix=".sqlite3") as database:
            engine = create_async_engine(f"sqlite+aiosqlite:///{database.name}", pool_size=1, max_overflow=0)
            connection = SQliteConnection(engine, {"driver": "sqlite"})
            started = asyncio.Event()

            async def cancelled_transaction():
                async with connection.transaction():
                    await connection.statement("CREATE TABLE cancelled (id INTEGER)")
                    started.set()
                    await asyncio.Event().wait()

            task = asyncio.create_task(cancelled_transaction())
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

            self.assertEqual(engine.pool.checkedout(), 0)  # type: ignore[attr-defined]
            self.assertEqual(await connection.select("SELECT 1 AS value"), [{"value": 1}])
            await engine.dispose()

    async def test_transaction_context_propagates_and_clean_context_is_isolated(self):
        conn = DB.connection("sqlite")
        async with conn.transaction():
            transaction_connection = await conn.get_connection()

            async def inherited_connection():
                return await conn.get_connection()

            async def clean_connection():
                connection = await conn.get_connection()
                try:
                    return connection
                finally:
                    await connection.close()

            inherited = await asyncio.create_task(inherited_connection())
            isolated = await Context().run(asyncio.create_task, clean_connection())

            self.assertIs(inherited, transaction_connection)
            self.assertIsNot(isolated, transaction_connection)

    async def test_rollback_undoes_insert(self):
        conn = DB.connection("sqlite")
        await conn.begin_transaction()
        await User.create({"email": "tx_test@example.com", "name": "TX Test", "is_admin": False})
        user = await User.where("email", "tx_test@example.com").first()
        assert user is not None
        await conn.rollback()
        user_after = await User.where("email", "tx_test@example.com").first()
        assert user_after is None

    async def test_commit_persists_insert(self):
        conn = DB.connection("sqlite")
        await conn.begin_transaction()
        await User.create({"email": "commit_test@example.com", "name": "Commit Test", "is_admin": False})
        await conn.commit_transaction()
        user = await User.where("email", "commit_test@example.com").first()
        assert user is not None

    async def test_nested_rollback_preserves_outer_transaction(self):
        conn = DB.connection("sqlite")
        await conn.begin_transaction()
        await User.create({"email": "outer@example.com", "name": "Outer", "is_admin": False})
        await conn.begin_transaction()
        await User.create({"email": "nested@example.com", "name": "Nested", "is_admin": False})
        await conn.rollback()

        assert await User.where("email", "nested@example.com").first() is None
        await conn.commit_transaction()

        assert await User.where("email", "outer@example.com").first() is not None
        assert await User.where("email", "nested@example.com").first() is None
