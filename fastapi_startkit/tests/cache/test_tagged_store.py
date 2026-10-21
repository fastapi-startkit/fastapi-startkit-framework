import tempfile
from unittest import IsolatedAsyncioTestCase

from fastapi_startkit.cache import ArrayStore, CacheManager, FileStore, MemoStore, Repository, TaggedStore


class TaggedContract:
    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()
        self.cache = Repository(self.store, "app")

    async def test_tagged_put_and_get(self):
        self.assertIs(await self.cache.tags(["people", "artists"]).put("john", "doe", 600), True)

        self.assertEqual(await self.cache.tags(["people", "artists"]).get("john"), "doe")

    async def test_untagged_and_other_tags_miss(self):
        await self.cache.tags(["people", "artists"]).put("john", "doe")

        self.assertIsNone(await self.cache.get("john"))
        self.assertIsNone(await self.cache.tags("people").get("john"))
        self.assertIsNone(await self.cache.tags(["people", "authors"]).get("john"))

    async def test_tag_order_and_duplicates_do_not_matter(self):
        await self.cache.tags(["people", "artists"]).put("john", "doe")

        self.assertEqual(await self.cache.tags(["artists", "people", "artists"]).get("john"), "doe")

    async def test_flush_invalidates_entries_carrying_any_flushed_tag(self):
        await self.cache.tags(["people", "artists"]).put("john", "doe")
        await self.cache.tags(["people", "authors"]).put("anne", "rice")
        await self.cache.tags("authors").put("mark", "twain")
        await self.cache.put("plain", "value")

        self.assertIs(await self.cache.tags("people").flush(), True)

        self.assertIsNone(await self.cache.tags(["people", "artists"]).get("john"))
        self.assertIsNone(await self.cache.tags(["people", "authors"]).get("anne"))
        self.assertEqual(await self.cache.tags("authors").get("mark"), "twain")
        self.assertEqual(await self.cache.get("plain"), "value")

    async def test_tag_ids_persist_in_the_store_with_prefix(self):
        await self.cache.tags("people").put("john", "doe")
        identifier = await self.cache.get("tag:people:key")

        self.assertIsInstance(identifier, str)
        self.assertEqual(await Repository(self.store, "app").tags("people").get("john"), "doe")

        await self.cache.tags("people").flush()

        self.assertNotEqual(await self.cache.get("tag:people:key"), identifier)

    async def test_forget_removes_only_the_tagged_key(self):
        await self.cache.tags("people").put("john", "doe")
        await self.cache.tags("people").put("jane", "roe")
        await self.cache.put("john", "plain")

        self.assertIs(await self.cache.tags("people").forget("john"), True)

        self.assertIsNone(await self.cache.tags("people").get("john"))
        self.assertEqual(await self.cache.tags("people").get("jane"), "roe")
        self.assertEqual(await self.cache.get("john"), "plain")

    async def test_remember_is_tagged(self):
        calls = []

        def load():
            calls.append(1)
            return ["post"]

        self.assertEqual(await self.cache.tags("posts").remember("user:1", 600, load), ["post"])
        self.assertEqual(await self.cache.tags("posts").remember("user:1", 600, load), ["post"])
        self.assertEqual(len(calls), 1)

        await self.cache.tags("posts").flush()

        await self.cache.tags("posts").remember("user:1", 600, load)
        self.assertEqual(len(calls), 2)

    async def test_decorator_is_tagged(self):
        calls = []

        @self.cache.tags("users").remember("user", 600)
        async def find(user_id):
            calls.append(user_id)
            return {"id": user_id}

        self.assertEqual(await find(1), {"id": 1})
        self.assertEqual(await find(1), {"id": 1})
        self.assertEqual(calls, [1])


class TestArrayTags(TaggedContract, IsolatedAsyncioTestCase):
    def make_store(self):
        return ArrayStore()


class TestFileTags(TaggedContract, IsolatedAsyncioTestCase):
    def make_store(self):
        return FileStore(self.enterContext(tempfile.TemporaryDirectory()))


class TestRepositoryTags(IsolatedAsyncioTestCase):
    async def test_tags_wraps_store_and_keeps_prefix(self):
        store = ArrayStore()

        tagged = Repository(store, "app").tags(["b", "a", "b"])

        self.assertIsInstance(tagged.store, TaggedStore)
        self.assertIs(tagged.store.store, store)
        self.assertEqual(tagged.store.tags.names, ["a", "b"])
        self.assertEqual(tagged.prefix, "app")

    async def test_empty_tags_raise(self):
        with self.assertRaises(ValueError):
            Repository(ArrayStore()).tags([])

    async def test_tags_work_on_memo_repository(self):
        manager = CacheManager({"default": "array", "stores": {"array": {"driver": "array"}}})

        await manager.memo().tags("people").put("john", "doe")

        self.assertIsInstance(manager.memo().store, MemoStore)
        self.assertEqual(await manager.tags("people").get("john"), "doe")
        self.assertEqual(await manager.memo().tags("people").get("john"), "doe")
