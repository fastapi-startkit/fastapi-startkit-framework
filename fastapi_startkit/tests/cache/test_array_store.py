from fastapi_startkit.cache import MISSING, ArrayStore


async def test_missing_key_returns_sentinel():
    assert await ArrayStore().get("name") is MISSING


async def test_put_and_get_keep_the_same_object():
    store = ArrayStore()
    value = {"roles": ["admin"]}

    assert await store.put("user", value, 60) is True
    assert await store.get("user") is value


async def test_cached_none_is_a_hit():
    store = ArrayStore()
    await store.put("nothing", None, None)

    assert await store.get("nothing") is None


async def test_entry_expires(clock):
    store = ArrayStore()
    await store.put("name", "taylor", 10)

    clock.travel(9)
    assert await store.get("name") == "taylor"

    clock.travel(1)
    assert await store.get("name") is MISSING
    assert "name" not in store.storage


async def test_forever_never_expires(clock):
    store = ArrayStore()
    await store.put("name", "taylor", None)

    clock.travel(10**9)

    assert await store.get("name") == "taylor"


async def test_forget_reports_whether_key_existed():
    store = ArrayStore()
    await store.put("name", "taylor", None)

    assert await store.forget("name") is True
    assert await store.forget("name") is False
    assert await store.get("name") is MISSING


async def test_flush_clears_everything():
    store = ArrayStore()
    await store.put("a", 1, None)
    await store.put("b", 2, None)

    assert await store.flush() is True
    assert store.storage == {}
