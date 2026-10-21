from dataclasses import asdict

import pytest

from fastapi_startkit.cache import ArrayStoreConfig, CacheConfig, DatabaseStoreConfig, FileStoreConfig

ENV = ("CACHE_CONNECTION", "CACHE_PREFIX", "CACHE_FILE_PATH", "DB_CACHE_CONNECTION", "DB_CACHE_TABLE")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    config = CacheConfig()

    assert config.default == "database"
    assert config.prefix == "cache"
    assert config.stores == {
        "array": ArrayStoreConfig(),
        "file": FileStoreConfig(path="storage/framework/cache/data"),
        "database": DatabaseStoreConfig(connection=None, table="caches"),
    }


def test_reads_environment(monkeypatch):
    monkeypatch.setenv("CACHE_CONNECTION", "file")
    monkeypatch.setenv("CACHE_PREFIX", "shop")
    monkeypatch.setenv("CACHE_FILE_PATH", "var/cache")
    monkeypatch.setenv("DB_CACHE_CONNECTION", "sqlite")
    monkeypatch.setenv("DB_CACHE_TABLE", "cache_entries")

    config = CacheConfig()

    assert config.default == "file"
    assert config.prefix == "shop"
    assert config.stores["file"] == FileStoreConfig(path="var/cache")
    assert config.stores["database"] == DatabaseStoreConfig(connection="sqlite", table="cache_entries")


def test_store_drivers():
    assert {name: getattr(store, "driver") for name, store in CacheConfig().stores.items()} == {
        "array": "array",
        "file": "file",
        "database": "database",
    }


def test_environment_is_read_per_instance(monkeypatch):
    before = CacheConfig()
    monkeypatch.setenv("CACHE_PREFIX", "later")

    assert before.prefix == "cache"
    assert CacheConfig().prefix == "later"


@pytest.mark.parametrize("name", ["CACHE_CONNECTION", "CACHE_PREFIX"])
def test_empty_environment_value_falls_back_to_default(monkeypatch, name):
    monkeypatch.setenv(name, "")

    config = CacheConfig()

    assert (config.default, config.prefix) == ("database", "cache")


def test_empty_store_environment_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("CACHE_FILE_PATH", "")
    monkeypatch.setenv("DB_CACHE_TABLE", "")

    assert FileStoreConfig().path == "storage/framework/cache/data"
    assert DatabaseStoreConfig().table == "caches"


@pytest.mark.parametrize("raw", ["1", "true", "mysql"])
def test_database_connection_name_is_never_cast(monkeypatch, raw):
    monkeypatch.setenv("DB_CACHE_CONNECTION", raw)

    assert DatabaseStoreConfig().connection == raw


def test_explicit_arguments_override_environment(monkeypatch):
    monkeypatch.setenv("CACHE_CONNECTION", "file")
    monkeypatch.setenv("CACHE_PREFIX", "shop")

    config = CacheConfig(default="array", prefix="", stores={"array": ArrayStoreConfig()})

    assert config.default == "array"
    assert config.prefix == ""
    assert config.stores == {"array": ArrayStoreConfig()}


def test_instances_do_not_share_stores():
    first = CacheConfig()
    second = CacheConfig()

    first.stores["redis"] = ArrayStoreConfig()

    assert "redis" not in second.stores
    assert first.stores["file"] is not second.stores["file"]


def test_class_attributes_resolve_environment(monkeypatch):
    monkeypatch.setenv("CACHE_PREFIX", "shop")
    monkeypatch.setenv("DB_CACHE_TABLE", "cache_entries")

    assert CacheConfig.prefix == "shop"
    assert CacheConfig.default == "database"
    assert DatabaseStoreConfig.table == "cache_entries"


def test_unknown_class_attribute_raises():
    with pytest.raises(AttributeError, match="has no attribute 'missing'"):
        getattr(CacheConfig, "missing")


def test_converts_to_nested_dict(monkeypatch):
    monkeypatch.setenv("CACHE_FILE_PATH", "var/cache")

    assert asdict(CacheConfig()) == {
        "default": "database",
        "prefix": "cache",
        "stores": {
            "array": {"driver": "array"},
            "file": {"driver": "file", "path": "var/cache"},
            "database": {"driver": "database", "connection": None, "table": "caches"},
        },
    }
