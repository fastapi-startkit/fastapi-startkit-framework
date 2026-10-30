import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.application import Application
from fastapi_startkit.cache import ArrayStoreConfig, CacheManager, CacheProvider, FileStore
from fastapi_startkit.configuration import config
from fastapi_startkit.facades import Cache


@dataclass
class ArrayCacheConfig:
    default: str = "array"
    prefix: str = "shop"
    stores: dict = field(default_factory=lambda: {"array": ArrayStoreConfig(), "second": ArrayStoreConfig()})


class TestCacheProvider(IsolatedAsyncioTestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        for name in ("CACHE_CONNECTION", "CACHE_FILE_PATH"):
            os.environ.pop(name, None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def make_app(self, provider=(CacheProvider, ArrayCacheConfig)):
        return Application(base_path=self.base_path, providers=[provider])

    def test_binds_manager_and_merges_default_config(self):
        app = self.make_app(CacheProvider)

        self.assertIsInstance(app.make("cache"), CacheManager)
        self.assertEqual(config("cache.default"), "database")
        self.assertEqual(config("cache.stores.database.table"), "caches")

    def test_plain_dataclass_config_is_accepted(self):
        app = self.make_app()

        self.assertEqual(app.make("cache").config["prefix"], "shop")
        self.assertEqual(config("cache.stores.second.driver"), "array")

    async def test_file_store_lives_under_base_path(self):
        self.make_app(CacheProvider)

        repository = Cache.store("file")
        await repository.put("name", "taylor")

        self.assertIsInstance(repository.store, FileStore)
        self.assertEqual(repository.store.directory, self.base_path / "storage/framework/cache/data")
        self.assertTrue(repository.store.path("cache:name").is_file())
        self.assertEqual(await Cache.store("file").get("name"), "taylor")

    def test_publishes_config_stub(self):
        app = self.make_app()

        self.assertIn("config/cache.py", app.published_resources["cache"].values())

    async def test_facade_proxies_to_manager(self):
        app = self.make_app()

        await Cache.put("name", "taylor", 60)
        await Cache.store("second").put("name", "otwell")

        self.assertEqual(await Cache.get("name"), "taylor")
        self.assertEqual(await Cache.store("second").get("name"), "otwell")
        self.assertIs(await Cache.has("name"), True)
        self.assertEqual(await Cache.get("missing", lambda: "fallback"), "fallback")
        self.assertIs(Cache.store(), app.make("cache").store())

    async def test_facade_remember_with_factory(self):
        self.make_app()

        async def factory():
            return "computed"

        self.assertEqual(await Cache.remember("value", 60, factory), "computed")
        self.assertEqual(await Cache.remember("value", 60, lambda: "other"), "computed")

    async def test_facade_decorator_resolves_the_container_per_call(self):
        calls = []

        @Cache.remember("users", 60)
        async def users(role):
            calls.append(role)
            return [role]

        first = self.make_app()
        self.assertEqual(await users("admin"), ["admin"])
        self.assertEqual(await users("admin"), ["admin"])
        self.assertEqual(calls, ["admin"])
        self.assertEqual(users.__name__, "users")

        second = self.make_app()
        self.assertEqual(await users("admin"), ["admin"])
        self.assertEqual(calls, ["admin", "admin"])
        self.assertIsNot(first.make("cache"), second.make("cache"))
