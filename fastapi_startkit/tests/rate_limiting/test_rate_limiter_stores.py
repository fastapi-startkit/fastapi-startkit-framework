import importlib.util
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

import fakeredis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastapi_startkit.cache import ArrayStore, FileStore, Repository
from fastapi_startkit.cache.database_store import DatabaseStore
from fastapi_startkit.cache.redis_store import RedisStore
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.schema import Schema
from fastapi_startkit.rate_limiting import RateLimiter
from fastapi_startkit.redis import RedisManager

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "src/fastapi_startkit/cache/migrations/2026_10_21_000000_create_caches_table.py"
)


class StoreContract:
    async def make_store(self):
        raise NotImplementedError

    async def asyncSetUp(self):
        self.clock = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        store = await self.make_store()
        self.limiter = RateLimiter(lambda: Repository(store, "limiter"))

    async def test_limits_and_resets_after_the_decay_window(self):
        for _ in range(3):
            await self.limiter.hit("login", 60)

        self.assertTrue(await self.limiter.too_many_attempts("login", 3))
        self.assertEqual(await self.limiter.available_in("login"), 60)

        self.clock.return_value += 60

        self.assertFalse(await self.limiter.too_many_attempts("login", 3))
        self.assertEqual(await self.limiter.hit("login", 60), 1)

    async def test_keys_are_independent_and_clearable(self):
        await self.limiter.hit("a")
        await self.limiter.hit("a")
        await self.limiter.hit("b")

        await self.limiter.clear("a")

        self.assertEqual(await self.limiter.attempts("a"), 0)
        self.assertEqual(await self.limiter.attempts("b"), 1)


class TestArrayStore(StoreContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        return ArrayStore()


class TestFileStore(StoreContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        return FileStore(self.enterContext(tempfile.TemporaryDirectory()))


class TestDatabaseStore(StoreContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.addAsyncCleanup(engine.dispose)
        connection = SQliteConnection(engine, SQLiteConfig(database=":memory:"))
        database = mock.Mock(connection=lambda name=None: connection)
        database.get_schema_builder = lambda: Schema(database)

        spec = importlib.util.spec_from_file_location("create_caches_table", MIGRATION)
        assert spec and spec.loader
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with mock.patch.object(migration, "config", return_value=None):
            await migration.CreateCachesTable("sqlite", database.get_schema_builder()).up()
        return DatabaseStore(lambda: connection)


class TestRedisStore(StoreContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        server = fakeredis.FakeServer()
        manager = RedisManager({"client": "fake", "connections": {"cache": {"database": 1}}}).extend(
            "fake", lambda parameters: fakeredis.FakeAsyncRedis(server=server, **parameters)
        )
        return RedisStore(lambda: manager.connection("cache"), "limiter")
