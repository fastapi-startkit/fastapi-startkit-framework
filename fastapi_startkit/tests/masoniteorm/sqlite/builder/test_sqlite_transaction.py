import asyncio

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
