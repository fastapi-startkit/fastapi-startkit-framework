from fastapi_startkit.redis import RedisConfig
from fastapi_startkit.redis.config import default_prefix


def test_defaults_mirror_laravel(monkeypatch):
    for name in ("REDIS_CLIENT", "REDIS_PREFIX", "REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_CACHE_DB"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("APP_NAME", "My Shop")

    config = RedisConfig()

    assert config.client == "redis"
    assert config.options == {"prefix": "my_shop_database_"}
    assert set(config.connections) == {"default", "cache"}
    assert config.connections["default"] == {
        "url": None,
        "host": "127.0.0.1",
        "username": None,
        "password": None,
        "port": 6379,
        "database": 0,
    }
    assert config.connections["cache"]["database"] == 1


def test_reads_environment(monkeypatch):
    monkeypatch.setenv("REDIS_CLIENT", "fake")
    monkeypatch.setenv("REDIS_PREFIX", "custom:")
    monkeypatch.setenv("REDIS_URL", "redis://cache.internal:6380/2")
    monkeypatch.setenv("REDIS_HOST", "redis.internal")
    monkeypatch.setenv("REDIS_USERNAME", "admin")
    monkeypatch.setenv("REDIS_PASSWORD", "secret")
    monkeypatch.setenv("REDIS_PORT", "6390")
    monkeypatch.setenv("REDIS_DB", "3")
    monkeypatch.setenv("REDIS_CACHE_DB", "4")

    config = RedisConfig()

    assert config.client == "fake"
    assert config.options["prefix"] == "custom:"
    default = config.connections["default"]
    assert default["url"] == "redis://cache.internal:6380/2"
    assert default["host"] == "redis.internal"
    assert default["username"] == "admin"
    assert default["password"] == "secret"
    assert default["port"] == 6390
    assert default["database"] == 3
    assert config.connections["cache"]["database"] == 4


def test_default_prefix_slugs_app_name(monkeypatch):
    monkeypatch.setenv("APP_NAME", "FastAPI  Starter-Kit!")
    assert default_prefix() == "fastapi_starter_kit_database_"
