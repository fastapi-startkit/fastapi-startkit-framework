import threading
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import ArrayStore, CacheManager, Repository


class TestRememberDecorator(IsolatedAsyncioTestCase):
    def setUp(self):
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.store = ArrayStore()
        self.cache = Repository(self.store, "app")

    async def test_caches_async_function_result(self):
        calls = []

        @self.cache.remember("users", 60)
        async def users():
            calls.append(1)
            return ["taylor"]

        self.assertEqual(await users(), ["taylor"])
        self.assertEqual(await users(), ["taylor"])
        self.assertEqual(calls, [1])
        self.assertEqual(list(self.store.storage), ["app:users"])

    async def test_wraps_sync_function_into_async(self):
        @self.cache.remember("total", 60)
        def total():
            return 42

        self.assertEqual(await total(), 42)
        self.assertEqual(total.__name__, "total")

    async def test_awaits_awaitable_returned_by_sync_function(self):
        async def query():
            return "rows"

        @self.cache.remember("rows", 60)
        def rows():
            return query()

        self.assertEqual(await rows(), "rows")

    async def test_each_argument_set_gets_its_own_key(self):
        calls = []

        @self.cache.remember("users", 60)
        async def users_by_role(role, active=True):
            calls.append((role, active))
            return f"{role}:{active}"

        self.assertEqual(await users_by_role("admin"), "admin:True")
        self.assertEqual(await users_by_role("admin"), "admin:True")
        self.assertEqual(await users_by_role("editor"), "editor:True")
        self.assertEqual(await users_by_role("admin", active=False), "admin:False")
        self.assertEqual(await users_by_role("admin", active=False), "admin:False")

        self.assertEqual(calls, [("admin", True), ("editor", True), ("admin", False)])
        self.assertEqual(len(self.store.storage), 3)
        self.assertTrue(all(key.startswith("app:users:") for key in self.store.storage))

    async def test_keyword_order_does_not_change_the_key(self):
        calls = []

        @self.cache.remember("sum", 60)
        def add(**numbers):
            calls.append(1)
            return sum(numbers.values())

        self.assertEqual(await add(a=1, b=2), 3)
        self.assertEqual(await add(b=2, a=1), 3)
        self.assertEqual(calls, [1])

    async def test_unpicklable_arguments_fall_back_to_repr(self):
        lock = threading.Lock()

        @self.cache.remember("locked", 60)
        def locked(value):
            return value is lock

        self.assertIs(await locked(lock), True)
        self.assertIs(await locked(lock), True)

    async def test_key_defaults_to_function_path(self):
        @self.cache.remember(None, 60)
        def answer():
            return 42

        self.assertEqual(await answer(), 42)
        self.assertEqual(
            list(self.store.storage),
            [f"app:{__name__}.TestRememberDecorator.test_key_defaults_to_function_path.<locals>.answer"],
        )

    async def test_expires_with_ttl(self):
        values = iter(["first", "second"])

        @self.cache.remember("value", 10)
        def value():
            return next(values)

        self.assertEqual(await value(), "first")
        self.time.return_value += 10
        self.assertEqual(await value(), "second")

    async def test_shares_entries_with_callable_form(self):
        @self.cache.remember("users", 60)
        def users():
            return "decorated"

        await self.cache.put("users", "cached")

        self.assertEqual(await users(), "cached")
        self.assertEqual(await self.cache.remember("users", 60, lambda: "factory"), "cached")

    def test_factory_form_requires_a_key(self):
        with self.assertRaisesRegex(ValueError, "requires a key"):
            self.cache.remember(None, 60, lambda: 1)  # pyright: ignore[reportCallIssue, reportArgumentType]

    async def test_manager_proxies_decorator_to_default_store(self):
        manager = CacheManager({"default": "array", "stores": {"array": {"driver": "array"}}})

        @manager.remember("name", 60)
        def name():
            return "taylor"

        self.assertEqual(await name(), "taylor")
        self.assertEqual(await manager.get("name"), "taylor")
