from unittest import IsolatedAsyncioTestCase

from fastapi_startkit.cache import ArrayStore, CacheConfig, CacheManager, Repository
from fastapi_startkit.support.dataclass import Dataclass


def make_manager(**overrides):
    config = {
        "default": "array",
        "prefix": "app",
        "stores": {"array": {"driver": "array"}, "other": {"driver": "array"}},
    }
    config.update(overrides)
    return CacheManager(config)


class TestCacheManager(IsolatedAsyncioTestCase):
    def test_store_resolves_default_and_caches_repository(self):
        manager = make_manager()

        repository = manager.store()

        self.assertIsInstance(repository, Repository)
        self.assertIsInstance(repository.store, ArrayStore)
        self.assertEqual(repository.prefix, "app")
        self.assertIs(manager.store("array"), repository)
        self.assertIsNot(manager.store("other"), repository)

    async def test_named_stores_are_isolated(self):
        manager = make_manager()

        await manager.store("array").put("name", "taylor")

        self.assertIsNone(await manager.store("other").get("name"))

    async def test_unknown_attributes_proxy_to_default_store(self):
        manager = make_manager()

        await manager.put("name", "taylor")

        self.assertEqual(await manager.get("name"), "taylor")
        self.assertEqual(await manager.store("array").get("name"), "taylor")
        self.assertEqual(await manager.remember("name", 60, lambda: "other"), "taylor")

    def test_private_attributes_are_not_proxied(self):
        with self.assertRaises(AttributeError):
            make_manager()._missing

    def test_undefined_store_raises(self):
        with self.assertRaisesRegex(ValueError, r"Cache store \[redis\] is not defined."):
            make_manager().store("redis")

    def test_unsupported_driver_raises(self):
        manager = make_manager(stores={"file": {"driver": "file"}}, default="file")

        with self.assertRaisesRegex(ValueError, r"Cache driver \[file\] is not supported."):
            manager.store()

    async def test_extend_registers_custom_driver(self):
        created = []

        def factory(config):
            created.append(config)
            return ArrayStore()

        manager = make_manager(stores={"custom": {"driver": "custom", "size": 5}}, default="custom")

        self.assertIs(manager.extend("custom", factory), manager)
        await manager.put("name", "taylor")

        self.assertEqual(created, [{"driver": "custom", "size": 5}])
        self.assertEqual(await manager.get("name"), "taylor")

    async def test_accepts_resolved_cache_config(self):
        config = {**Dataclass.to_dict(CacheConfig()), "default": "array"}

        manager = CacheManager(config)
        await manager.put("name", "taylor")

        self.assertEqual(await manager.store("array").get("name"), "taylor")
