from dataclasses import dataclass, field

from fastapi_startkit.application import Application
from fastapi_startkit.cache import ArrayStoreConfig, CacheManager, CacheProvider, FileStore
from fastapi_startkit.configuration import config
from fastapi_startkit.facades import Cache


@dataclass
class ArrayCacheConfig:
    default: str = "array"
    prefix: str = "shop"
    stores: dict = field(default_factory=lambda: {"array": ArrayStoreConfig(), "second": ArrayStoreConfig()})


def make_app(tmp_path, provider=(CacheProvider, ArrayCacheConfig)):
    return Application(base_path=tmp_path, env="testing", providers=[provider])


def test_binds_manager_and_merges_default_config(tmp_path, monkeypatch):
    monkeypatch.delenv("CACHE_CONNECTION", raising=False)
    app = make_app(tmp_path, CacheProvider)

    assert isinstance(app.make("cache"), CacheManager)
    assert config("cache.default") == "file"
    assert config("cache.stores.database.table") == "caches"


def test_plain_dataclass_config_is_accepted(tmp_path):
    app = make_app(tmp_path)

    assert app.make("cache").config["prefix"] == "shop"
    assert config("cache.stores.second.driver") == "array"


async def test_file_store_lives_under_base_path(tmp_path, monkeypatch):
    monkeypatch.delenv("CACHE_FILE_PATH", raising=False)
    make_app(tmp_path, CacheProvider)

    repository = Cache.store("file")
    await repository.put("name", "taylor")

    assert isinstance(repository.store, FileStore)
    assert repository.store.directory == tmp_path / "storage/framework/cache/data"
    assert repository.store.path("cache:name").is_file()
    assert await Cache.store("file").get("name") == "taylor"


def test_publishes_config_stub(tmp_path):
    app = make_app(tmp_path)

    assert "config/cache.py" in app.published_resources["cache"].values()


async def test_facade_proxies_to_manager(tmp_path):
    app = make_app(tmp_path)

    await Cache.put("name", "taylor", 60)
    await Cache.store("second").put("name", "otwell")

    assert await Cache.get("name") == "taylor"
    assert await Cache.store("second").get("name") == "otwell"
    assert await Cache.has("name") is True
    assert await Cache.get("missing", lambda: "fallback") == "fallback"
    assert Cache.store() is app.make("cache").store()


async def test_facade_remember_with_factory(tmp_path):
    make_app(tmp_path)

    async def factory():
        return "computed"

    assert await Cache.remember("value", 60, factory) == "computed"
    assert await Cache.remember("value", 60, lambda: "other") == "computed"


async def test_facade_decorator_resolves_the_container_per_call(tmp_path):
    calls = []

    @Cache.remember("users", 60)
    async def users(role):
        calls.append(role)
        return [role]

    first = make_app(tmp_path)
    assert await users("admin") == ["admin"]
    assert await users("admin") == ["admin"]
    assert calls == ["admin"]
    assert users.__name__ == "users"

    second = make_app(tmp_path)
    assert await users("admin") == ["admin"]
    assert calls == ["admin", "admin"]
    assert first.make("cache") is not second.make("cache")
