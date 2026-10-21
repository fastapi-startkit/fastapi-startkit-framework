from fastapi_startkit.cache import ArrayStoreConfig, CacheConfig, DatabaseStoreConfig, FileStoreConfig

ENV = ("CACHE_CONNECTION", "CACHE_PREFIX", "CACHE_FILE_PATH", "DB_CACHE_CONNECTION", "DB_CACHE_TABLE")


def test_defaults(monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)

    config = CacheConfig()

    assert config.default == "file"
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
