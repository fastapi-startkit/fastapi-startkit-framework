import asyncio
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import ArrayStore, FileStore, LockTimeoutError, Repository
from fastapi_startkit.cache.database_store import DatabaseStore

from test_database_store import InMemoryDatabase, load_migration


class LockContract:
    async def make_store(self):
        raise NotImplementedError

    async def asyncSetUp(self):
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.store = await self.make_store()

    def lock(self, seconds=10, owner=None):
        lock = self.store.lock("reports", seconds, owner)
        lock.sleep = 0.01
        return lock

    async def test_acquires_once(self):
        self.assertIs(await self.lock().get(), True)
        self.assertIs(await self.lock().get(), False)

    async def test_is_not_reentrant(self):
        lock = self.lock()

        self.assertIs(await lock.get(), True)
        self.assertIs(await lock.get(), False)

    async def test_expired_lock_can_be_taken(self):
        await self.lock(seconds=10).get()

        self.time.return_value += 11

        self.assertIs(await self.lock().get(), True)

    async def test_zero_seconds_never_expires(self):
        await self.lock(seconds=0).get()

        self.time.return_value += 10**9

        self.assertIs(await self.lock().get(), False)

    async def test_release_only_by_owner(self):
        lock = self.lock()
        await lock.get()

        self.assertIs(await self.lock().release(), False)
        self.assertIs(await self.lock().get(), False)
        self.assertIs(await lock.release(), True)
        self.assertIs(await lock.release(), False)
        self.assertIs(await self.lock().get(), True)

    async def test_release_of_own_expired_lock_returns_false(self):
        lock = self.lock(seconds=10)
        await lock.get()

        self.time.return_value += 11

        self.assertIs(await lock.release(), False)
        self.assertIs(await self.lock().get(), True)

    async def test_concurrent_acquires_have_exactly_one_winner(self):
        results = await asyncio.gather(*(self.lock().get() for _ in range(10)))

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 9)

    async def test_force_release_ignores_owner(self):
        await self.lock().get()

        await self.lock().force_release()

        self.assertIs(await self.lock().get(), True)

    async def test_restored_owner_can_release(self):
        lock = self.lock()
        await lock.get()

        self.assertIs(await self.lock(owner=lock.owner).release(), True)
        self.assertIs(await self.lock().get(), True)

    async def test_get_runs_sync_callback_and_releases(self):
        self.assertEqual(await self.lock().get(lambda: "done"), "done")
        self.assertIs(await self.lock().get(), True)

    async def test_get_runs_async_callback_and_releases(self):
        async def build():
            return "done"

        self.assertEqual(await self.lock().get(build), "done")
        self.assertIs(await self.lock().get(), True)

    async def test_get_skips_callback_when_held(self):
        callback = mock.Mock()
        await self.lock().get()

        self.assertIs(await self.lock().get(callback), False)
        callback.assert_not_called()

    async def test_get_releases_when_callback_fails(self):
        def fail():
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            await self.lock().get(fail)

        self.assertIs(await self.lock().get(), True)

    async def test_block_waits_for_release(self):
        holder = self.lock()
        await holder.get()
        waits = []
        sleep = asyncio.sleep

        async def release_while_waiting(seconds):
            waits.append(seconds)
            await holder.release()
            await sleep(0)

        with mock.patch("asyncio.sleep", release_while_waiting):
            self.assertEqual(await self.lock().block(2, lambda: "done"), "done")

        self.assertEqual(waits, [0.01])
        self.assertIs(await self.lock().get(), True)

    async def test_block_times_out(self):
        await self.lock().get()

        with self.assertRaises(LockTimeoutError):
            await self.lock().block(0.05)

    async def test_block_returns_true_without_callback(self):
        self.assertIs(await self.lock().block(1), True)

    async def test_async_with_acquires_and_releases(self):
        async with self.lock():
            self.assertIs(await self.lock().get(), False)

        self.assertIs(await self.lock().get(), True)

    async def test_async_with_releases_when_body_raises(self):
        with self.assertRaises(RuntimeError):
            async with self.lock():
                raise RuntimeError("boom")

        self.assertIs(await self.lock().get(), True)

    async def test_async_with_raises_when_held(self):
        await self.lock().get()

        with self.assertRaises(LockTimeoutError):
            async with self.lock():
                self.fail("body must not run")


class TestArrayLock(LockContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        return ArrayStore()


class TestFileLock(LockContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        return FileStore(directory)

    async def test_flush_keeps_locks(self):
        await self.lock().get()

        await self.store.flush()

        self.assertIs(await self.lock().get(), False)

    async def test_corrupt_lock_file_counts_as_free(self):
        lock = self.lock()
        lock.path.parent.mkdir(parents=True)
        lock.path.write_bytes(b"not json")

        self.assertIs(await lock.get(), True)

    async def test_release_truncates_instead_of_unlinking(self):
        lock = self.lock()
        await lock.get()

        await lock.release()

        self.assertEqual(Path(lock.path).read_bytes(), b"")


class TestDatabaseLock(LockContract, IsolatedAsyncioTestCase):
    async def make_store(self):
        self.database = InMemoryDatabase()
        self.addAsyncCleanup(self.database.engine.dispose)
        migration = load_migration()
        with mock.patch.object(migration, "config", return_value=None):
            await migration.CreateCachesTable("sqlite", self.database.get_schema_builder()).up()
        return DatabaseStore(self.database.connection)

    async def test_lock_row_does_not_collide_with_cache_key(self):
        await self.store.put("reports", "cached", None)

        self.assertIs(await self.lock().get(), True)
        self.assertEqual(await self.store.get("reports"), "cached")


class TestRepositoryLock(IsolatedAsyncioTestCase):
    async def test_prefixes_lock_name(self):
        store = ArrayStore()

        await Repository(store, "app").lock("reports", 10).get()

        self.assertIn("app:reports", store.locks)

    async def test_store_without_locks_raises(self):
        class PlainStore:
            pass

        with self.assertRaises(TypeError):
            Repository(PlainStore()).lock("reports")  # pyright: ignore[reportArgumentType]
