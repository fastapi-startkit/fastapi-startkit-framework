import sys

import pytest

from fastapi_startkit.redis import Connection, RedisManager, RedisNotInstalledError
from fastapi_startkit.redis.connector import connect

from .conftest import make_config


def test_connection_defaults_to_default_and_is_cached(manager):
    connection = manager.connection()

    assert isinstance(connection, Connection)
    assert connection.name == "default"
    assert manager.connection("default") is connection
    assert manager.connections() == {"default": connection}


def test_named_connections_resolve_to_separate_clients(manager):
    assert manager.connection("cache").client is not manager.connection().client


async def test_named_connections_use_their_own_database(manager):
    await manager.connection().set("key", "default")
    await manager.connection("cache").set("key", "cache")

    assert await manager.connection().get("key") == "default"
    assert await manager.connection("cache").get("key") == "cache"


def test_unknown_connection_raises(manager):
    with pytest.raises(ValueError, match=r"Redis connection \[missing\] not configured."):
        manager.connection("missing")


def test_unsupported_client_raises():
    with pytest.raises(ValueError, match=r"Redis client \[fake\] is not supported."):
        RedisManager(make_config()).connection()


async def test_prefix_is_applied_to_keys(manager, raw):
    await manager.set("name", "taylor")

    assert await raw.keys("*") == ["app_name"]
    assert await manager.get("name") == "taylor"


async def test_connection_options_override_global_prefix(factory, raw):
    config = make_config()
    config["connections"]["cache"]["options"] = {"prefix": "cache_"}
    manager = RedisManager(config).extend("fake", factory)

    await manager.connection("cache").set("name", "taylor")

    assert await manager.connection("cache").get("name") == "taylor"
    assert manager.connection("cache").prefix == "cache_"


async def test_empty_prefix_stores_raw_keys(factory, raw):
    manager = RedisManager(make_config(prefix="")).extend("fake", factory)

    await manager.set("name", "taylor")

    assert await raw.keys("*") == ["name"]


def test_client_parameters_are_normalised():
    received = []
    config = make_config(prefix="")
    config["connections"]["default"].update({"password": None, "url": None, "socket_timeout": 3})
    RedisManager(config).extend("fake", lambda parameters: received.append(parameters) or object()).connection()

    assert received == [
        {"decode_responses": True, "host": "127.0.0.1", "port": 6379, "db": 0, "socket_timeout": 3},
    ]


def test_decode_responses_can_be_disabled():
    received = []
    config = make_config(prefix="")
    config["connections"]["default"]["decode_responses"] = False
    RedisManager(config).extend("fake", lambda parameters: received.append(parameters) or object()).connection()

    assert received[0]["decode_responses"] is False


def test_manager_proxies_to_default_connection(manager):
    assert manager.ping == manager.connection().ping


def test_private_attributes_are_not_proxied(manager):
    with pytest.raises(AttributeError):
        manager._missing


async def test_purge_closes_and_forgets_connection(manager):
    connection = manager.connection()

    await manager.purge()

    assert manager.connections() == {}
    assert manager.connection() is not connection


async def test_purge_unknown_connection_is_noop(manager):
    await manager.purge("cache")
    assert manager.connections() == {}


async def test_disconnect_closes_every_connection(manager):
    manager.connection()
    manager.connection("cache")

    await manager.disconnect()

    assert manager.connections() == {}


def test_connect_builds_redis_client_from_parameters():
    client = connect({"host": "redis.internal", "port": 6390, "db": 2, "decode_responses": True})

    kwargs = client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("redis.internal", 6390, 2)


def test_connect_prefers_url_over_parameters():
    client = connect({"url": "redis://cache.internal:6381/5", "host": "ignored", "decode_responses": True})

    kwargs = client.connection_pool.connection_kwargs
    assert (kwargs["host"], kwargs["port"], kwargs["db"]) == ("cache.internal", 6381, 5)


def test_unix_socket_url_drops_tcp_parameters():
    config = make_config(client="redis", prefix="")
    config["connections"]["default"].update(
        {"url": "unix:///tmp/redis.sock", "username": "user", "password": "secret", "database": 2}
    )

    kwargs = RedisManager(config).connection().client.connection_pool.connection_kwargs

    assert kwargs["path"] == "/tmp/redis.sock"
    assert kwargs["db"] == 2
    assert "host" not in kwargs and "port" not in kwargs
    assert (kwargs["username"], kwargs["password"]) == ("user", "secret")


def test_configured_password_applies_when_url_has_none():
    config = make_config(client="redis", prefix="")
    config["connections"]["default"].update({"url": "redis://redis:6379", "password": "secret"})

    kwargs = RedisManager(config).connection().client.connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["port"], kwargs["password"]) == ("redis", 6379, "secret")


def test_url_credentials_override_configured_ones():
    config = make_config(client="redis", prefix="")
    config["connections"]["default"].update({"url": "redis://:fromurl@cache.internal:6381", "password": "ignored"})

    kwargs = RedisManager(config).connection().client.connection_pool.connection_kwargs

    assert (kwargs["host"], kwargs["port"], kwargs["password"]) == ("cache.internal", 6381, "fromurl")


def test_missing_redis_package_raises_helpful_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "redis.asyncio", None)

    with pytest.raises(RedisNotInstalledError, match=r"fastapi-startkit\[redis\]"):
        RedisManager(make_config(client="redis")).connection()
