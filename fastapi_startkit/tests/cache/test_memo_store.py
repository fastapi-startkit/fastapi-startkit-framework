import asyncio
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import MISSING, ArrayStore, CacheManager, MemoStore


class TestMemoStore(IsolatedAsyncioTestCase):
    def setUp(self):
        self.inner = ArrayStore()
        self.reads = self.enterContext(mock.patch.object(self.inner, "get", wraps=self.inner.get))
        self.store = MemoStore(self.inner)

    async def test_repeated_get_reads_inner_store_once(self):
        await self.inner.put("name", "taylor", None)

        self.assertEqual(await self.store.get("name"), "taylor")
        self.assertEqual(await self.store.get("name"), "taylor")
        self.assertEqual(self.reads.await_count, 1)

    async def test_miss_is_memoized(self):
        self.assertIs(await self.store.get("name"), MISSING)
        self.assertIs(await self.store.get("name"), MISSING)
        self.assertEqual(self.reads.await_count, 1)

    async def test_memoized_value_survives_inner_change(self):
        await self.inner.put("name", "taylor", None)
        await self.store.get("name")

        await self.inner.put("name", "abigail", None)

        self.assertEqual(await self.store.get("name"), "taylor")

    async def test_put_writes_through_and_invalidates(self):
        await self.store.get("name")

        self.assertIs(await self.store.put("name", "taylor", 60), True)

        self.assertEqual(await self.inner.get("name"), "taylor")
        self.assertEqual(await self.store.get("name"), "taylor")
        self.assertEqual(self.reads.await_count, 3)

    async def test_forget_writes_through_and_invalidates(self):
        await self.inner.put("name", "taylor", None)
        await self.store.get("name")

        self.assertIs(await self.store.forget("name"), True)

        self.assertIs(await self.store.get("name"), MISSING)

    async def test_flush_clears_memo_and_inner_store(self):
        await self.inner.put("name", "taylor", None)
        await self.store.get("name")

        self.assertIs(await self.store.flush(), True)

        self.assertEqual(self.inner.storage, {})
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_tasks_do_not_share_memo(self):
        await self.inner.put("name", "taylor", None)
        await self.store.get("name")

        await asyncio.gather(self.store.get("name"), self.store.get("name"))

        self.assertEqual(self.reads.await_count, 3)

    async def test_stores_keep_separate_memos(self):
        other = MemoStore(ArrayStore())
        await self.inner.put("name", "taylor", None)

        await self.store.get("name")

        self.assertIs(await other.get("name"), MISSING)


class TestManagerMemo(IsolatedAsyncioTestCase):
    def setUp(self):
        self.manager = CacheManager(
            {
                "default": "array",
                "prefix": "app",
                "stores": {"array": {"driver": "array"}, "other": {"driver": "array"}},
            }
        )

    async def test_memo_wraps_default_store_with_prefix(self):
        repository = self.manager.memo()

        self.assertIsInstance(repository.store, MemoStore)
        self.assertIs(repository.store.store, self.manager.store().store)
        self.assertEqual(repository.prefix, "app")

    async def test_memo_is_cached_per_store(self):
        self.assertIs(self.manager.memo(), self.manager.memo("array"))
        self.assertIsNot(self.manager.memo(), self.manager.memo("other"))

    async def test_memo_reads_through_to_the_store(self):
        await self.manager.put("name", "taylor")

        self.assertEqual(await self.manager.memo().get("name"), "taylor")
        self.assertEqual(await self.manager.memo().remember("count", 60, lambda: 1), 1)
        self.assertEqual(await self.manager.get("count"), 1)
