from datetime import timedelta

import pytest

from fastapi_startkit.cache import ArrayStore, Repository


@pytest.fixture
def store():
    return ArrayStore()


@pytest.fixture
def cache(store):
    return Repository(store, "app")


async def test_keys_are_prefixed(cache, store):
    await cache.put("name", "taylor")

    assert list(store.storage) == ["app:name"]
    assert await cache.get("name") == "taylor"


async def test_no_prefix(store):
    await Repository(store).put("name", "taylor")

    assert list(store.storage) == ["name"]


async def test_get_returns_default_on_miss(cache):
    assert await cache.get("missing") is None
    assert await cache.get("missing", "fallback") == "fallback"


async def test_get_calls_sync_and_async_defaults_only_on_miss(cache):
    calls = []

    def sync_default():
        calls.append("sync")
        return "sync"

    async def async_default():
        calls.append("async")
        return "async"

    assert await cache.get("missing", sync_default) == "sync"
    assert await cache.get("missing", async_default) == "async"

    await cache.put("present", "value")
    assert await cache.get("present", sync_default) == "value"
    assert calls == ["sync", "async"]


async def test_cached_none_is_not_replaced_by_default(cache):
    await cache.put("nothing", None)

    assert await cache.has("nothing") is True
    assert await cache.get("nothing", "fallback") is None


async def test_ttl_accepts_seconds_and_timedelta(cache, clock):
    await cache.put("seconds", 1, 60)
    await cache.put("delta", 2, timedelta(minutes=2))

    clock.travel(61)
    assert await cache.has("seconds") is False
    assert await cache.get("delta") == 2

    clock.travel(60)
    assert await cache.has("delta") is False


async def test_non_positive_ttl_forgets_the_key(cache):
    await cache.put("name", "taylor")

    assert await cache.put("name", "otwell", 0) is False
    assert await cache.has("name") is False
    assert await cache.put("name", "otwell", timedelta(seconds=-1)) is False


async def test_forever(cache, clock):
    assert await cache.forever("name", "taylor") is True

    clock.travel(10**9)

    assert await cache.get("name") == "taylor"


async def test_forget_and_flush(cache):
    await cache.put("a", 1)
    await cache.put("b", 2)

    assert await cache.forget("a") is True
    assert await cache.has("a") is False

    assert await cache.flush() is True
    assert await cache.has("b") is False


async def test_remember_runs_factory_once(cache):
    calls = []

    def factory():
        calls.append(1)
        return ["taylor"]

    assert await cache.remember("users", 60, factory) == ["taylor"]
    assert await cache.remember("users", 60, factory) == ["taylor"]
    assert calls == [1]


async def test_remember_awaits_async_factory(cache):
    async def factory():
        return "computed"

    assert await cache.remember("value", 60, factory) == "computed"
    assert await cache.get("value") == "computed"


async def test_remember_awaits_awaitable_returned_by_sync_factory(cache):
    async def query():
        return "rows"

    assert await cache.remember("rows", 60, lambda: query()) == "rows"


async def test_remember_caches_none(cache):
    calls = []

    def factory():
        calls.append(1)

    await cache.remember("nothing", 60, factory)
    await cache.remember("nothing", 60, factory)

    assert calls == [1]


async def test_remember_recomputes_after_expiry(cache, clock):
    values = iter(["first", "second"])

    assert await cache.remember("value", 10, lambda: next(values)) == "first"
    clock.travel(10)
    assert await cache.remember("value", 10, lambda: next(values)) == "second"
