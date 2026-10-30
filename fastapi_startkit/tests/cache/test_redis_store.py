import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

import fakeredis

from fastapi_startkit.application import Application
from fastapi_startkit.cache import MISSING, CacheProvider, RedisStoreConfig
from fastapi_startkit.cache.redis_store import RedisStore
from fastapi_startkit.facades import Cache
from fastapi_startkit.redis import RedisManager, RedisProvider


@dataclass
class User:
    name: str


def redis_config(prefix="app_"):
    return {
        "client": "fake",
        "options": {"prefix": prefix},
        "connections": {"default": {"database": 0}, "cache": {"database": 1}},
    }


@dataclass
class RedisCacheConfig:
    default: str = "redis"
    prefix: str = "shop"
    stores: dict = field(
        default_factory=lambda: {"redis": RedisStoreConfig(), "other": RedisStoreConfig(connection="default")}
    )


class RedisStoreTestCase(IsolatedAsyncioTestCase):
    prefix = "app_"

    def setUp(self):
        self.server = fakeredis.FakeServer()
        self.manager = RedisManager(redis_config(self.prefix)).extend("fake", self.client)
        self.raw = fakeredis.FakeAsyncRedis(server=self.server, db=1, decode_responses=True)
        self.store = RedisStore(lambda: self.manager.connection("cache"), "shop")

    def client(self, parameters):
        return fakeredis.FakeAsyncRedis(server=self.server, **parameters)


class TestRedisStore(RedisStoreTestCase):
    async def test_missing_key_returns_sentinel(self):
        self.assertIs(await self.store.get("shop:name"), MISSING)

    async def test_round_trips_python_objects(self):
        self.assertIs(await self.store.put("shop:user", User("taylor"), 60), True)

        self.assertEqual(await self.store.get("shop:user"), User("taylor"))

    async def test_cached_none_is_a_hit(self):
        await self.store.put("shop:nothing", None, None)

        self.assertIsNone(await self.store.get("shop:nothing"))

    async def test_writes_through_the_connection_prefix_and_database(self):
        await self.store.put("shop:name", "taylor", None)

        self.assertEqual(await self.raw.keys("*"), ["app_shop:name"])
        self.assertEqual(await self.raw.ttl("app_shop:name"), -1)

    async def test_ttl_is_set_in_milliseconds(self):
        await self.store.put("shop:name", "taylor", 1.5)

        self.assertIn(await self.raw.pttl("app_shop:name"), range(1400, 1501))

    async def test_sub_millisecond_ttl_rounds_up_to_one_millisecond(self):
        connection = self.manager.connection("cache")
        with mock.patch.object(connection.client, "set", wraps=connection.client.set) as set_:
            await self.store.put("shop:name", "taylor", 0.0001)

        self.assertEqual(set_.call_args.kwargs["px"], 1)

    async def test_corrupt_payload_is_a_miss_and_removed(self):
        await self.raw.set("app_shop:name", "not-base64-pickle")

        self.assertIs(await self.store.get("shop:name"), MISSING)
        self.assertEqual(await self.raw.exists("app_shop:name"), 0)

    async def test_forget(self):
        await self.store.put("shop:name", "taylor", None)

        self.assertIs(await self.store.forget("shop:name"), True)
        self.assertIs(await self.store.forget("shop:name"), False)
        self.assertIs(await self.store.get("shop:name"), MISSING)

    async def test_flush_removes_only_prefixed_keys(self):
        self.store.batch = 2
        for index in range(5):
            await self.store.put(f"shop:{index}", index, None)
        await self.raw.set("app_shopping", "kept")
        await self.raw.set("app_other:1", "kept")
        await self.raw.set("shop:1", "kept")

        self.assertIs(await self.store.flush(), True)

        self.assertEqual(sorted(await self.raw.keys("*")), ["app_other:1", "app_shopping", "shop:1"])

    async def test_flush_never_calls_flushdb(self):
        connection = self.manager.connection("cache")
        with (
            mock.patch.object(connection.client, "flushdb") as flushdb,
            mock.patch.object(connection.client, "flushall") as flushall,
        ):
            await self.store.flush()

        flushdb.assert_not_called()
        flushall.assert_not_called()

    async def test_flush_escapes_glob_characters_in_prefix(self):
        store = RedisStore(lambda: self.manager.connection("cache"), "s*[a]")
        await store.put("s*[a]:name", "taylor", None)
        await self.raw.set("app_sx[a]:name", "kept")
        await self.raw.set("app_sa:name", "kept")

        await store.flush()

        self.assertEqual(sorted(await self.raw.keys("*")), ["app_sa:name", "app_sx[a]:name"])

    def test_empty_prefix_is_rejected(self):
        with self.assertRaises(ValueError):
            RedisStore(lambda: self.manager.connection("cache"), "")


class TestRedisStoreWithoutConnectionPrefix(RedisStoreTestCase):
    prefix = ""

    async def test_flush_removes_only_prefixed_keys(self):
        await self.store.put("shop:name", "taylor", None)
        await self.raw.set("other", "kept")

        await self.store.flush()

        self.assertEqual(await self.raw.keys("*"), ["other"])


class TestRedisCacheProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        os.environ.pop("CACHE_CONNECTION", None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.server = fakeredis.FakeServer()

    def make_app(self):
        app = Application(
            base_path=self.base_path,
            providers=[(RedisProvider, lambda: redis_config()), (CacheProvider, RedisCacheConfig)],
        )
        app.make("redis").extend("fake", lambda parameters: fakeredis.FakeAsyncRedis(server=self.server, **parameters))
        return app

    def database(self, number):
        return fakeredis.FakeAsyncRedis(server=self.server, db=number, decode_responses=True)

    def test_default_store_config_uses_the_cache_connection(self):
        self.assertEqual(RedisStoreConfig().connection, "cache")

    async def test_cache_store_redis_uses_the_named_redis_connection(self):
        self.make_app()

        await Cache.store("redis").put("name", "taylor", 60)

        self.assertIsInstance(Cache.store("redis").store, RedisStore)
        self.assertEqual(await Cache.store("redis").get("name"), "taylor")
        self.assertEqual(await self.database(1).keys("*"), ["app_shop:name"])

    async def test_store_connection_is_selectable(self):
        self.make_app()

        await Cache.store("other").put("name", "taylor")

        self.assertEqual(await self.database(0).keys("*"), ["app_shop:name"])

    async def test_flush_through_facade_keeps_unrelated_keys(self):
        self.make_app()
        await self.database(1).set("app_queue:1", "job")

        await Cache.put("name", "taylor")
        await Cache.flush()

        self.assertEqual(await self.database(1).keys("*"), ["app_queue:1"])

    async def test_missing_redis_provider_raises_on_first_use(self):
        Application(base_path=self.base_path, providers=[(CacheProvider, RedisCacheConfig)])

        repository = Cache.store("redis")

        with self.assertRaisesRegex(RuntimeError, "RedisProvider"):
            await repository.get("name")
