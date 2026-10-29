from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import MISSING, ArrayStore


class TestArrayStore(IsolatedAsyncioTestCase):
    def setUp(self):
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.store = ArrayStore()

    async def test_missing_key_returns_sentinel(self):
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_put_and_get_keep_the_same_object(self):
        value = {"roles": ["admin"]}

        self.assertIs(await self.store.put("user", value, 60), True)
        self.assertIs(await self.store.get("user"), value)

    async def test_cached_none_is_a_hit(self):
        await self.store.put("nothing", None, None)

        self.assertIsNone(await self.store.get("nothing"))

    async def test_entry_expires(self):
        await self.store.put("name", "taylor", 10)

        self.time.return_value += 9
        self.assertEqual(await self.store.get("name"), "taylor")

        self.time.return_value += 1
        self.assertIs(await self.store.get("name"), MISSING)
        self.assertNotIn("name", self.store.storage)

    async def test_forever_never_expires(self):
        await self.store.put("name", "taylor", None)

        self.time.return_value += 10**9

        self.assertEqual(await self.store.get("name"), "taylor")

    async def test_forget_reports_whether_key_existed(self):
        await self.store.put("name", "taylor", None)

        self.assertIs(await self.store.forget("name"), True)
        self.assertIs(await self.store.forget("name"), False)
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_flush_clears_everything(self):
        await self.store.put("a", 1, None)
        await self.store.put("b", 2, None)

        self.assertIs(await self.store.flush(), True)
        self.assertEqual(self.store.storage, {})
