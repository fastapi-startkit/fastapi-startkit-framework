from datetime import timedelta
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import ArrayStore, Repository


class TestRepository(IsolatedAsyncioTestCase):
    def setUp(self):
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.store = ArrayStore()
        self.cache = Repository(self.store, "app")

    async def test_keys_are_prefixed(self):
        await self.cache.put("name", "taylor")

        self.assertEqual(list(self.store.storage), ["app:name"])
        self.assertEqual(await self.cache.get("name"), "taylor")

    async def test_no_prefix(self):
        await Repository(self.store).put("name", "taylor")

        self.assertEqual(list(self.store.storage), ["name"])

    async def test_get_returns_default_on_miss(self):
        self.assertIsNone(await self.cache.get("missing"))
        self.assertEqual(await self.cache.get("missing", "fallback"), "fallback")

    async def test_get_calls_sync_and_async_defaults_only_on_miss(self):
        calls = []

        def sync_default():
            calls.append("sync")
            return "sync"

        async def async_default():
            calls.append("async")
            return "async"

        self.assertEqual(await self.cache.get("missing", sync_default), "sync")
        self.assertEqual(await self.cache.get("missing", async_default), "async")

        await self.cache.put("present", "value")
        self.assertEqual(await self.cache.get("present", sync_default), "value")
        self.assertEqual(calls, ["sync", "async"])

    async def test_cached_none_is_not_replaced_by_default(self):
        await self.cache.put("nothing", None)

        self.assertIs(await self.cache.has("nothing"), True)
        self.assertIsNone(await self.cache.get("nothing", "fallback"))

    async def test_ttl_accepts_seconds_and_timedelta(self):
        await self.cache.put("seconds", 1, 60)
        await self.cache.put("delta", 2, timedelta(minutes=2))

        self.time.return_value += 61
        self.assertIs(await self.cache.has("seconds"), False)
        self.assertEqual(await self.cache.get("delta"), 2)

        self.time.return_value += 60
        self.assertIs(await self.cache.has("delta"), False)

    async def test_non_positive_ttl_forgets_the_key(self):
        await self.cache.put("name", "taylor")

        self.assertIs(await self.cache.put("name", "otwell", 0), False)
        self.assertIs(await self.cache.has("name"), False)
        self.assertIs(await self.cache.put("name", "otwell", timedelta(seconds=-1)), False)

    async def test_forever(self):
        self.assertIs(await self.cache.forever("name", "taylor"), True)

        self.time.return_value += 10**9

        self.assertEqual(await self.cache.get("name"), "taylor")

    async def test_forget_and_flush(self):
        await self.cache.put("a", 1)
        await self.cache.put("b", 2)

        self.assertIs(await self.cache.forget("a"), True)
        self.assertIs(await self.cache.has("a"), False)

        self.assertIs(await self.cache.flush(), True)
        self.assertIs(await self.cache.has("b"), False)

    async def test_remember_runs_factory_once(self):
        calls = []

        def factory():
            calls.append(1)
            return ["taylor"]

        self.assertEqual(await self.cache.remember("users", 60, factory), ["taylor"])
        self.assertEqual(await self.cache.remember("users", 60, factory), ["taylor"])
        self.assertEqual(calls, [1])

    async def test_remember_awaits_async_factory(self):
        async def factory():
            return "computed"

        self.assertEqual(await self.cache.remember("value", 60, factory), "computed")
        self.assertEqual(await self.cache.get("value"), "computed")

    async def test_remember_awaits_awaitable_returned_by_sync_factory(self):
        async def query():
            return "rows"

        self.assertEqual(await self.cache.remember("rows", 60, lambda: query()), "rows")

    async def test_remember_caches_none(self):
        calls = []

        def factory():
            calls.append(1)

        await self.cache.remember("nothing", 60, factory)
        await self.cache.remember("nothing", 60, factory)

        self.assertEqual(calls, [1])

    async def test_remember_recomputes_after_expiry(self):
        values = iter(["first", "second"])

        self.assertEqual(await self.cache.remember("value", 10, lambda: next(values)), "first")
        self.time.return_value += 10
        self.assertEqual(await self.cache.remember("value", 10, lambda: next(values)), "second")
