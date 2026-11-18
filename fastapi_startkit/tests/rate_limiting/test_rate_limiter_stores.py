import asyncio
import importlib.util
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

import fakeredis
from sqlalchemy.ext.asyncio import create_async_engine

from starlette.requests import Request
from starlette.responses import Response

from fastapi_startkit.application import Application
from fastapi_startkit.cache import ArrayStore, FileStore, Repository
from fastapi_startkit.cache.database_store import DatabaseStore
from fastapi_startkit.cache.redis_store import RedisStore
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.schema import Schema
from fastapi_startkit.container.container import Container
from fastapi_startkit.exceptions import ThrottleRequestsException
from fastapi_startkit.rate_limiting import Limit, RateLimiter, RateLimiterProvider, throttle
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
        self.other_worker = RateLimiter(lambda: Repository(store, "limiter"))

    def bind_application(self):
        original_instance = Container._instance
        self.addCleanup(lambda: setattr(Container, "_instance", original_instance))
        base_path = self.enterContext(tempfile.TemporaryDirectory())
        Application(base_path=base_path, providers=[RateLimiterProvider]).bind("rate_limiter", self.limiter)

    async def test_concurrent_hits_are_all_counted(self):
        results = await asyncio.gather(*(self.limiter.hit("login") for _ in range(10)))

        self.assertEqual(sorted(results), list(range(1, 11)))
        self.assertEqual(await self.limiter.attempts("login"), 10)

    async def test_concurrent_hits_from_separate_limiters_are_all_counted(self):
        workers = [self.limiter, self.other_worker] * 10

        await asyncio.gather(*(worker.hit("login") for worker in workers))

        self.assertEqual(await self.limiter.attempts("login"), 20)

    async def test_concurrent_attempts_from_separate_limiters_admit_exactly_max_attempts(self):
        workers = [self.limiter, self.other_worker] * 10

        results = await asyncio.gather(*(worker.attempt("login", 5, lambda: True) for worker in workers))

        self.assertEqual(results.count(True), 5)

    async def test_concurrent_attempts_admit_exactly_max_attempts(self):
        results = await asyncio.gather(*(self.limiter.attempt("login", 5, lambda: True) for _ in range(20)))

        self.assertEqual(results.count(True), 5)

    def throttled_request(self):
        self.bind_application()
        self.limiter.for_("login", lambda request: [Limit.per_minute(5).by("ip"), Limit.per_hour(50).by("ip")])
        dependency = throttle("login")

        async def request():
            try:
                await dependency(Request({"type": "http", "headers": []}), Response())
            except ThrottleRequestsException:
                return False
            return True

        return request

    async def test_concurrent_throttle_bursts_admit_max_attempts_per_window(self):
        request = self.throttled_request()

        for _ in range(3):
            results = await asyncio.gather(*(request() for _ in range(20)))
            self.assertEqual(results.count(True), 5)
            self.clock.return_value += 60

    async def test_concurrent_throttle_bursts_in_one_window_admit_max_attempts_in_total(self):
        request = self.throttled_request()

        bursts = await asyncio.gather(*(asyncio.gather(*(request() for _ in range(20))) for _ in range(3)))

        self.assertEqual(sum(results.count(True) for results in bursts), 5)

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
        config = SQLiteConfig(database=str(Path(self.enterContext(tempfile.TemporaryDirectory())) / "cache.sqlite"))
        engine = create_async_engine(config.build_url(), **config.engine_options())
        self.addAsyncCleanup(engine.dispose)
        connection = SQliteConnection(engine, config)
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
