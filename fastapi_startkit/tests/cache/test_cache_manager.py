import pytest

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


def test_store_resolves_default_and_caches_repository():
    manager = make_manager()

    repository = manager.store()

    assert isinstance(repository, Repository)
    assert isinstance(repository.store, ArrayStore)
    assert repository.prefix == "app"
    assert manager.store("array") is repository
    assert manager.store("other") is not repository


async def test_named_stores_are_isolated():
    manager = make_manager()

    await manager.store("array").put("name", "taylor")

    assert await manager.store("other").get("name") is None


async def test_unknown_attributes_proxy_to_default_store():
    manager = make_manager()

    await manager.put("name", "taylor")

    assert await manager.get("name") == "taylor"
    assert await manager.store("array").get("name") == "taylor"
    assert await manager.remember("name", 60, lambda: "other") == "taylor"


def test_private_attributes_are_not_proxied():
    with pytest.raises(AttributeError):
        make_manager()._missing


def test_undefined_store_raises():
    with pytest.raises(ValueError, match=r"Cache store \[redis\] is not defined."):
        make_manager().store("redis")


def test_unsupported_driver_raises():
    manager = make_manager(stores={"file": {"driver": "file"}}, default="file")

    with pytest.raises(ValueError, match=r"Cache driver \[file\] is not supported."):
        manager.store()


async def test_extend_registers_custom_driver():
    created = []

    def factory(config):
        created.append(config)
        return ArrayStore()

    manager = make_manager(stores={"custom": {"driver": "custom", "size": 5}}, default="custom")

    assert manager.extend("custom", factory) is manager
    await manager.put("name", "taylor")

    assert created == [{"driver": "custom", "size": 5}]
    assert await manager.get("name") == "taylor"


async def test_accepts_resolved_cache_config():
    config = {**Dataclass.to_dict(CacheConfig()), "default": "array"}

    manager = CacheManager(config)
    await manager.put("name", "taylor")

    assert await manager.store("array").get("name") == "taylor"
