import os
import unittest
from dataclasses import asdict
from unittest import mock

from fastapi_startkit.cache import ArrayStoreConfig, CacheConfig, DatabaseStoreConfig, FileStoreConfig

ENV = ("CACHE_CONNECTION", "CACHE_PREFIX", "CACHE_FILE_PATH", "DB_CACHE_CONNECTION", "DB_CACHE_TABLE")


class TestCacheConfig(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.dict(os.environ))
        for name in ENV:
            os.environ.pop(name, None)

    def test_defaults(self):
        config = CacheConfig()

        self.assertEqual(config.default, "database")
        self.assertEqual(config.prefix, "cache")
        self.assertEqual(
            config.stores,
            {
                "array": ArrayStoreConfig(),
                "file": FileStoreConfig(path="storage/framework/cache/data"),
                "database": DatabaseStoreConfig(connection=None, table="caches"),
            },
        )

    def test_reads_environment(self):
        os.environ.update(
            CACHE_CONNECTION="file",
            CACHE_PREFIX="shop",
            CACHE_FILE_PATH="var/cache",
            DB_CACHE_CONNECTION="sqlite",
            DB_CACHE_TABLE="cache_entries",
        )

        config = CacheConfig()

        self.assertEqual(config.default, "file")
        self.assertEqual(config.prefix, "shop")
        self.assertEqual(config.stores["file"], FileStoreConfig(path="var/cache"))
        self.assertEqual(config.stores["database"], DatabaseStoreConfig(connection="sqlite", table="cache_entries"))

    def test_store_drivers(self):
        self.assertEqual(
            {name: getattr(store, "driver") for name, store in CacheConfig().stores.items()},
            {"array": "array", "file": "file", "database": "database"},
        )

    def test_environment_is_read_per_instance(self):
        before = CacheConfig()
        os.environ["CACHE_PREFIX"] = "later"

        self.assertEqual(before.prefix, "cache")
        self.assertEqual(CacheConfig().prefix, "later")

    def test_empty_environment_value_falls_back_to_default(self):
        for name in ("CACHE_CONNECTION", "CACHE_PREFIX"):
            with self.subTest(name=name), mock.patch.dict(os.environ, {name: ""}):
                config = CacheConfig()

                self.assertEqual((config.default, config.prefix), ("database", "cache"))

    def test_empty_store_environment_values_fall_back_to_defaults(self):
        os.environ.update(CACHE_FILE_PATH="", DB_CACHE_TABLE="")

        self.assertEqual(FileStoreConfig().path, "storage/framework/cache/data")
        self.assertEqual(DatabaseStoreConfig().table, "caches")

    def test_database_connection_name_is_never_cast(self):
        for raw in ("1", "true", "mysql"):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {"DB_CACHE_CONNECTION": raw}):
                self.assertEqual(DatabaseStoreConfig().connection, raw)

    def test_explicit_arguments_override_environment(self):
        os.environ.update(CACHE_CONNECTION="file", CACHE_PREFIX="shop")

        config = CacheConfig(default="array", prefix="", stores={"array": ArrayStoreConfig()})

        self.assertEqual(config.default, "array")
        self.assertEqual(config.prefix, "")
        self.assertEqual(config.stores, {"array": ArrayStoreConfig()})

    def test_instances_do_not_share_stores(self):
        first = CacheConfig()
        second = CacheConfig()

        first.stores["redis"] = ArrayStoreConfig()

        self.assertNotIn("redis", second.stores)
        self.assertIsNot(first.stores["file"], second.stores["file"])

    def test_class_attributes_resolve_environment(self):
        os.environ.update(CACHE_PREFIX="shop", DB_CACHE_TABLE="cache_entries")

        self.assertEqual(CacheConfig.prefix, "shop")
        self.assertEqual(CacheConfig.default, "database")
        self.assertEqual(DatabaseStoreConfig.table, "cache_entries")

    def test_unknown_class_attribute_raises(self):
        with self.assertRaisesRegex(AttributeError, "has no attribute 'missing'"):
            getattr(CacheConfig, "missing")

    def test_converts_to_nested_dict(self):
        os.environ["CACHE_FILE_PATH"] = "var/cache"

        self.assertEqual(
            asdict(CacheConfig()),
            {
                "default": "database",
                "prefix": "cache",
                "stores": {
                    "array": {"driver": "array"},
                    "file": {"driver": "file", "path": "var/cache"},
                    "database": {"driver": "database", "connection": None, "table": "caches"},
                },
            },
        )
