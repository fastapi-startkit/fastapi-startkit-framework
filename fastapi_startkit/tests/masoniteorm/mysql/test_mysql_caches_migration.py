import importlib.util
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from sqlalchemy.exc import IntegrityError

from fastapi_startkit.cache.database_store import DatabaseStore

from .fixtures.db import DB

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "src/fastapi_startkit/cache/migrations/2026_10_21_000000_create_caches_table.py"
)


def load_migration():
    spec = importlib.util.spec_from_file_location("create_caches_table", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMySQLCachesMigration(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        migration = load_migration()
        self.enterContext(mock.patch.object(migration, "config", return_value=None))
        self.schema = DB.get_schema_builder()
        await self.schema.drop_table_if_exists("caches")
        self.migration = migration.CreateCachesTable("mysql", self.schema)

    async def asyncTearDown(self):
        await self.schema.drop_table_if_exists("caches")
        await DB.clear()

    async def test_the_caches_migration_makes_key_the_primary_key_on_mysql(self):
        await self.migration.up()
        caches = DB.connection().query().table("caches")

        await caches.insert({"key": "greeting", "value": "bonjour", "expiration": None})

        with self.assertRaises(IntegrityError):
            await DB.connection().query().table("caches").insert({"key": "greeting", "value": "salut"})

    async def test_the_migrated_table_stores_values_by_key(self):
        await self.migration.up()
        store = DatabaseStore(DB.connection)

        await store.put("greeting", "bonjour", None)
        await store.put("greeting", "salut", 60)

        self.assertEqual(await store.get("greeting"), "salut")
        self.assertEqual(await store.connection().query().table("caches").count(), 1)
