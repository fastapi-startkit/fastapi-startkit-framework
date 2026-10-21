import threading

import pytest

from fastapi_startkit.cache import ArrayStore, CacheManager, Repository


@pytest.fixture
def store():
    return ArrayStore()


@pytest.fixture
def cache(store):
    return Repository(store, "app")


async def test_caches_async_function_result(cache, store):
    calls = []

    @cache.remember("users", 60)
    async def users():
        calls.append(1)
        return ["taylor"]

    assert await users() == ["taylor"]
    assert await users() == ["taylor"]
    assert calls == [1]
    assert list(store.storage) == ["app:users"]


async def test_wraps_sync_function_into_async(cache):
    @cache.remember("total", 60)
    def total():
        return 42

    assert await total() == 42
    assert total.__name__ == "total"


async def test_awaits_awaitable_returned_by_sync_function(cache):
    async def query():
        return "rows"

    @cache.remember("rows", 60)
    def rows():
        return query()

    assert await rows() == "rows"


async def test_each_argument_set_gets_its_own_key(cache, store):
    calls = []

    @cache.remember("users", 60)
    async def users_by_role(role, active=True):
        calls.append((role, active))
        return f"{role}:{active}"

    assert await users_by_role("admin") == "admin:True"
    assert await users_by_role("admin") == "admin:True"
    assert await users_by_role("editor") == "editor:True"
    assert await users_by_role("admin", active=False) == "admin:False"
    assert await users_by_role("admin", active=False) == "admin:False"

    assert calls == [("admin", True), ("editor", True), ("admin", False)]
    assert len(store.storage) == 3
    assert all(key.startswith("app:users:") for key in store.storage)


async def test_keyword_order_does_not_change_the_key(cache):
    calls = []

    @cache.remember("sum", 60)
    def add(**numbers):
        calls.append(1)
        return sum(numbers.values())

    assert await add(a=1, b=2) == 3
    assert await add(b=2, a=1) == 3
    assert calls == [1]


async def test_unpicklable_arguments_fall_back_to_repr(cache):
    lock = threading.Lock()

    @cache.remember("locked", 60)
    def locked(value):
        return value is lock

    assert await locked(lock) is True
    assert await locked(lock) is True


async def test_key_defaults_to_function_path(cache, store):
    @cache.remember(None, 60)
    def answer():
        return 42

    assert await answer() == 42
    assert list(store.storage) == [f"app:{__name__}.test_key_defaults_to_function_path.<locals>.answer"]


async def test_expires_with_ttl(cache, clock):
    values = iter(["first", "second"])

    @cache.remember("value", 10)
    def value():
        return next(values)

    assert await value() == "first"
    clock.travel(10)
    assert await value() == "second"


async def test_shares_entries_with_callable_form(cache):
    @cache.remember("users", 60)
    def users():
        return "decorated"

    await cache.put("users", "cached")

    assert await users() == "cached"
    assert await cache.remember("users", 60, lambda: "factory") == "cached"


def test_factory_form_requires_a_key(cache):
    with pytest.raises(ValueError, match="requires a key"):
        cache.remember(None, 60, lambda: 1)  # pyright: ignore[reportCallIssue, reportArgumentType]


async def test_manager_proxies_decorator_to_default_store():
    manager = CacheManager({"default": "array", "stores": {"array": {"driver": "array"}}})

    @manager.remember("name", 60)
    def name():
        return "taylor"

    assert await name() == "taylor"
    assert await manager.get("name") == "taylor"
