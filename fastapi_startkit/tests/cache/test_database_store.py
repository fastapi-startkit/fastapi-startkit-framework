import base64
import importlib.util
import pickle
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.cache import MISSING, CacheProvider
from fastapi_startkit.cache.database_store import DatabaseStore
from fastapi_startkit.facades import Cache
from fastapi_startkit.masoniteorm import DatabaseConfig, SQLiteConfig
from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory
from fastapi_startkit.masoniteorm.connections.manager import DatabaseManager
from fastapi_startkit.masoniteorm.providers import DatabaseProvider

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "src/fastapi_startkit/cache/migrations/2026_10_21_000000_create_caches_table.py"
)


@dataclass
class User:
    name: str


def database_config(path):
    return DatabaseConfig(default="sqlite", connections={"sqlite": SQLiteConfig(database=str(path))})


def migration_class():
    spec = importlib.util.spec_from_file_location("create_caches_table", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CreateCachesTable


async def migrate(db):
    await migration_class()("sqlite", db.get_schema_builder()).up()


@pytest.fixture
async def db(tmp_path):
    Application(base_path=tmp_path, env="testing")
    manager = DatabaseManager(ConnectionFactory(), database_config(tmp_path / "cache.sqlite3"))
    await migrate(manager)
    return manager


@pytest.fixture
def store(db):
    return DatabaseStore(lambda: db.connection(None))


async def rows(db):
    return await db.connection(None).select("SELECT * FROM caches")


async def test_missing_key_returns_sentinel(store):
    assert await store.get("name") is MISSING


async def test_round_trips_python_objects_as_base64_pickle(store, db):
    assert await store.put("user", User("taylor"), None) is True

    assert await store.get("user") == User("taylor")
    [row] = await rows(db)
    assert row["key"] == "user"
    assert pickle.loads(base64.b64decode(row["value"])) == User("taylor")
    assert row["expiration"] is None


async def test_cached_none_is_a_hit(store):
    await store.put("nothing", None, None)

    assert await store.get("nothing") is None


async def test_put_overwrites_without_duplicating(store, db):
    await store.put("name", "taylor", None)
    await store.put("name", "otwell", 60)

    assert await store.get("name") == "otwell"
    assert len(await rows(db)) == 1


async def test_put_survives_a_concurrent_insert(store, db, monkeypatch):
    original = store.query
    calls = []

    def racing_query():
        builder = original()
        calls.append(builder)
        if len(calls) == 1:

            async def no_rows(values):
                await (
                    db.connection(None).query().table("caches").insert({"key": "name", "value": "", "expiration": None})
                )
                return 0

            builder.update = no_rows
        return builder

    monkeypatch.setattr(store, "query", racing_query)

    assert await store.put("name", "taylor", None) is True

    monkeypatch.undo()
    assert await store.get("name") == "taylor"
    assert len(await rows(db)) == 1


async def test_entry_expires_and_row_is_removed(store, db, clock):
    await store.put("name", "taylor", 10)

    clock.travel(9)
    assert await store.get("name") == "taylor"

    clock.travel(1)
    assert await store.get("name") is MISSING
    assert await rows(db) == []


async def test_forever_never_expires(store, clock):
    await store.put("name", "taylor", None)

    clock.travel(10**9)

    assert await store.get("name") == "taylor"


async def test_corrupt_value_is_a_miss_and_removed(store, db):
    await (
        db.connection(None).query().table("caches").insert({"key": "name", "value": "not base64!", "expiration": None})
    )

    assert await store.get("name") is MISSING
    assert await rows(db) == []


@pytest.mark.parametrize("removal", ["module", "class"])
async def test_value_of_removed_class_is_a_miss_and_removed(store, db, monkeypatch, removal):
    module = types.ModuleType("cache_fixture_models")
    module.Gone = type("Gone", (), {"__module__": "cache_fixture_models"})
    monkeypatch.setitem(sys.modules, "cache_fixture_models", module)
    await store.put("gone", module.Gone(), None)

    if removal == "module":
        monkeypatch.delitem(sys.modules, "cache_fixture_models")
    else:
        monkeypatch.delattr(module, "Gone")

    assert await store.get("gone") is MISSING
    assert await rows(db) == []


async def test_expiration_column_is_big_integer(store, db, clock):
    columns = await db.connection(None).select("PRAGMA table_info(caches)")

    assert {column["name"]: column["type"] for column in columns}["expiration"].upper() == "BIGINT"

    await store.put("far", "future", 60 * 60 * 24 * 365 * 100)
    [row] = await rows(db)
    assert row["expiration"] > 2**31


async def test_forget_reports_whether_key_existed(store):
    await store.put("name", "taylor", None)

    assert await store.forget("name") is True
    assert await store.forget("name") is False


async def test_flush_removes_every_entry(store, db):
    await store.put("a", 1, None)
    await store.put("b", 2, None)

    assert await store.flush() is True

    assert await rows(db) == []


async def test_migration_down_drops_table(db):
    await migration_class()("sqlite", db.get_schema_builder()).down()

    assert not await db.get_schema_builder().has_table("caches")


async def test_provider_uses_database_store_by_default(tmp_path, monkeypatch):
    for name in ("CACHE_CONNECTION", "DB_CACHE_CONNECTION", "DB_CACHE_TABLE"):
        monkeypatch.delenv(name, raising=False)
    config = database_config(tmp_path / "app.sqlite3")
    app = Application(
        base_path=tmp_path,
        env="testing",
        providers=[(DatabaseProvider, lambda: config), CacheProvider],
    )
    await migrate(app.make("db"))

    await Cache.put("name", "taylor")

    assert isinstance(Cache.store().store, DatabaseStore)
    assert await Cache.get("name") == "taylor"
    [row] = await rows(app.make("db"))
    assert row["key"] == "cache:name"
    assert "databases/migrations/2026_10_21_000000_create_caches_table.py" in app.published_resources["cache"].values()


async def test_migration_follows_configured_table(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_CACHE_TABLE", "app_cache")
    monkeypatch.setenv("CACHE_CONNECTION", "database")
    config = database_config(tmp_path / "app.sqlite3")
    app = Application(
        base_path=tmp_path,
        env="testing",
        providers=[(DatabaseProvider, lambda: config), CacheProvider],
    )
    schema = app.make("db").get_schema_builder()

    await migrate(app.make("db"))
    await Cache.put("name", "taylor")

    assert await schema.has_table("app_cache")
    assert not await schema.has_table("caches")
    assert await Cache.get("name") == "taylor"
