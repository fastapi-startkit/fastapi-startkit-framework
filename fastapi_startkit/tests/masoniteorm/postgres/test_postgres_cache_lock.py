from unittest import mock

from fastapi_startkit.cache.database_store import DatabaseStore

from .fixtures.db import DB, schema
from .test_case import TestCase


class TestPostgresCacheLock(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await schema.drop_table_if_exists("caches")
        async with await schema.create("caches") as table:
            table.string("key").primary()
            table.text("value")
            table.big_integer("expiration").nullable()
        self.store = DatabaseStore(DB.connection)

    async def asyncTearDown(self):
        await schema.drop_table_if_exists("caches")
        await super().asyncTearDown()

    async def test_a_held_lock_is_refused_inside_an_open_transaction(self):
        async with DB.connection().transaction():
            self.assertIs(await self.store.lock("reports", 10).acquire(), True)
            self.assertIs(await self.store.lock("reports", 10).acquire(), False)
            self.assertEqual(await DB.connection().query().table("caches").count(), 1)

    async def test_an_expired_lock_is_taken_over_inside_an_open_transaction(self):
        async with DB.connection().transaction():
            await self.store.lock("reports", 10).acquire()

            with mock.patch("time.time", return_value=10**12):
                self.assertIs(await self.store.lock("reports", 10).acquire(), True)
