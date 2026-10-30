import base64
import importlib.util
import os
import pickle
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from fastapi_startkit.application import Application
from fastapi_startkit.cache import MISSING, CacheProvider
from fastapi_startkit.cache.database_store import DatabaseStore
from fastapi_startkit.facades import Cache
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.schema import Schema

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "src/fastapi_startkit/cache/migrations/2026_10_21_000000_create_caches_table.py"
)


@dataclass
class User:
    name: str


class InMemoryDatabase:
    def __init__(self):
        self.engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
        self.sqlite = SQliteConnection(self.engine, SQLiteConfig(database=":memory:"))

    def connection(self, name=None):
        return self.sqlite

    def get_schema_builder(self):
        return Schema(self)

    async def rows(self):
        return await self.sqlite.select("SELECT * FROM caches")


def load_migration():
    spec = importlib.util.spec_from_file_location("create_caches_table", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DatabaseTestCase(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database = InMemoryDatabase()
        self.migration = load_migration()

    async def asyncTearDown(self):
        await self.database.engine.dispose()

    def schema_migration(self):
        return self.migration.CreateCachesTable("sqlite", self.database.get_schema_builder())


class TestDatabaseStore(DatabaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.enterContext(mock.patch.object(self.migration, "config", return_value=None))
        await self.schema_migration().up()
        self.store = DatabaseStore(self.database.connection)

    async def insert(self, value):
        await (
            self.database.connection()
            .query()
            .table("caches")
            .insert({"key": "name", "value": value, "expiration": None})
        )

    async def test_missing_key_returns_sentinel(self):
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_round_trips_python_objects_as_base64_pickle(self):
        self.assertIs(await self.store.put("user", User("taylor"), None), True)

        self.assertEqual(await self.store.get("user"), User("taylor"))
        [row] = await self.database.rows()
        self.assertEqual(row["key"], "user")
        self.assertEqual(pickle.loads(base64.b64decode(row["value"])), User("taylor"))
        self.assertIsNone(row["expiration"])

    async def test_cached_none_is_a_hit(self):
        await self.store.put("nothing", None, None)

        self.assertIsNone(await self.store.get("nothing"))

    async def test_put_overwrites_without_duplicating(self):
        await self.store.put("name", "taylor", None)
        await self.store.put("name", "otwell", 60)

        self.assertEqual(await self.store.get("name"), "otwell")
        self.assertEqual(len(await self.database.rows()), 1)

    async def test_put_survives_a_concurrent_insert(self):
        original = self.store.query
        calls = []

        def racing_query():
            builder = original()
            calls.append(builder)
            if len(calls) == 1:

                async def no_rows(values):
                    await self.insert("")
                    return 0

                builder.update = no_rows
            return builder

        with mock.patch.object(self.store, "query", racing_query):
            self.assertIs(await self.store.put("name", "taylor", None), True)

        self.assertEqual(await self.store.get("name"), "taylor")
        self.assertEqual(len(await self.database.rows()), 1)

    async def test_entry_expires_and_row_is_removed(self):
        await self.store.put("name", "taylor", 10)

        self.time.return_value += 9
        self.assertEqual(await self.store.get("name"), "taylor")

        self.time.return_value += 1
        self.assertIs(await self.store.get("name"), MISSING)
        self.assertEqual(await self.database.rows(), [])

    async def test_forever_never_expires(self):
        await self.store.put("name", "taylor", None)

        self.time.return_value += 10**9

        self.assertEqual(await self.store.get("name"), "taylor")

    async def test_corrupt_value_is_a_miss_and_removed(self):
        await self.insert("not base64!")

        self.assertIs(await self.store.get("name"), MISSING)
        self.assertEqual(await self.database.rows(), [])

    async def test_value_of_removed_class_is_a_miss_and_removed(self):
        for removal in ("module", "class"):
            with self.subTest(removal=removal), mock.patch.dict(sys.modules):
                module = types.ModuleType("cache_fixture_models")
                setattr(module, "Gone", type("Gone", (), {"__module__": "cache_fixture_models"}))
                sys.modules["cache_fixture_models"] = module
                await self.store.put("gone", getattr(module, "Gone")(), None)

                if removal == "module":
                    del sys.modules["cache_fixture_models"]
                else:
                    delattr(module, "Gone")

                self.assertIs(await self.store.get("gone"), MISSING)
                self.assertEqual(await self.database.rows(), [])

    async def test_expiration_column_is_big_integer(self):
        columns = await self.database.sqlite.select("PRAGMA table_info(caches)")

        self.assertEqual({column["name"]: column["type"] for column in columns}["expiration"].upper(), "BIGINT")

        await self.store.put("far", "future", 60 * 60 * 24 * 365 * 100)
        [row] = await self.database.rows()
        self.assertGreater(row["expiration"], 2**31)

    async def test_forget_reports_whether_key_existed(self):
        await self.store.put("name", "taylor", None)

        self.assertIs(await self.store.forget("name"), True)
        self.assertIs(await self.store.forget("name"), False)

    async def test_flush_removes_every_entry(self):
        await self.store.put("a", 1, None)
        await self.store.put("b", 2, None)

        self.assertIs(await self.store.flush(), True)

        self.assertEqual(await self.database.rows(), [])

    async def test_migration_down_drops_table(self):
        await self.schema_migration().down()

        self.assertFalse(await self.database.get_schema_builder().has_table("caches"))


class TestDatabaseStoreProvider(DatabaseTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.enterContext(mock.patch.dict(os.environ))
        for name in ("CACHE_CONNECTION", "DB_CACHE_CONNECTION", "DB_CACHE_TABLE"):
            os.environ.pop(name, None)
        self.base_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def make_app(self):
        app = Application(base_path=self.base_path, providers=[CacheProvider])
        app.bind("db", self.database)
        return app

    async def test_provider_uses_database_store_by_default(self):
        app = self.make_app()
        await self.schema_migration().up()

        await Cache.put("name", "taylor")

        self.assertIsInstance(Cache.store().store, DatabaseStore)
        self.assertEqual(await Cache.get("name"), "taylor")
        [row] = await self.database.rows()
        self.assertEqual(row["key"], "cache:name")
        self.assertIn(
            "databases/migrations/2026_10_21_000000_create_caches_table.py",
            app.published_resources["cache"].values(),
        )

    async def test_migration_follows_configured_table(self):
        os.environ["DB_CACHE_TABLE"] = "app_cache"
        os.environ["CACHE_CONNECTION"] = "database"
        self.make_app()
        schema = self.database.get_schema_builder()

        await self.schema_migration().up()
        await Cache.put("name", "taylor")

        self.assertTrue(await schema.has_table("app_cache"))
        self.assertFalse(await schema.has_table("caches"))
        self.assertEqual(await Cache.get("name"), "taylor")
