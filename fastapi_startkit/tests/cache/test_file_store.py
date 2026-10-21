import hashlib
import pickle
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from unittest import IsolatedAsyncioTestCase, mock

from fastapi_startkit.cache import MISSING, FileStore


@dataclass
class User:
    name: str


class TestFileStore(IsolatedAsyncioTestCase):
    def setUp(self):
        self.time = self.enterContext(mock.patch("time.time", return_value=1_000_000.0))
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.directory = self.root / "cache"
        self.store = FileStore(self.directory)

    def files(self):
        return sorted(path.name for path in self.directory.rglob("*") if path.is_file())

    async def test_missing_key_returns_sentinel(self):
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_round_trips_python_objects(self):
        self.assertIs(await self.store.put("user", User("taylor"), 60), True)

        self.assertEqual(await self.store.get("user"), User("taylor"))

    async def test_layout_uses_sharded_sha1_paths(self):
        await self.store.put("name", "taylor", None)
        digest = hashlib.sha1(b"name").hexdigest()

        path = self.directory / digest[:2] / digest[2:4] / digest
        self.assertTrue(path.is_file())
        self.assertEqual(pickle.loads(path.read_bytes()), (None, "taylor"))

    async def test_cached_none_is_a_hit(self):
        await self.store.put("nothing", None, None)

        self.assertIsNone(await self.store.get("nothing"))

    async def test_entry_expires_and_file_is_removed(self):
        await self.store.put("name", "taylor", 10)

        self.time.return_value += 9
        self.assertEqual(await self.store.get("name"), "taylor")

        self.time.return_value += 1
        self.assertIs(await self.store.get("name"), MISSING)
        self.assertEqual(self.files(), [])

    async def test_forever_never_expires(self):
        await self.store.put("name", "taylor", None)

        self.time.return_value += 10**9

        self.assertEqual(await self.store.get("name"), "taylor")

    async def test_put_overwrites(self):
        await self.store.put("name", "taylor", None)
        await self.store.put("name", "otwell", None)

        self.assertEqual(await self.store.get("name"), "otwell")

    async def test_write_is_atomic_and_leaves_no_temporary_file(self):
        await self.store.put("name", "taylor", None)

        with mock.patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                await self.store.put("name", "otwell", None)

        self.assertEqual(await self.store.get("name"), "taylor")
        self.assertEqual(len(self.files()), 1)

    async def test_unpicklable_value_raises_without_writing(self):
        with self.assertRaises((pickle.PicklingError, TypeError, AttributeError)):
            await self.store.put("lambda", lambda: 1, None)

        self.assertEqual(self.files(), [])

    async def test_corrupt_file_is_a_miss_and_removed(self):
        await self.store.put("name", "taylor", None)
        self.store.path("name").write_bytes(b"not a pickle")

        self.assertIs(await self.store.get("name"), MISSING)
        self.assertEqual(self.files(), [])

    async def test_value_of_removed_class_is_a_miss_and_removed(self):
        for removal in ("module", "class"):
            with self.subTest(removal=removal), mock.patch.dict(sys.modules):
                module = types.ModuleType("cache_fixture_models")
                setattr(module, "Gone", type("Gone", (), {"__module__": "cache_fixture_models"}))
                sys.modules["cache_fixture_models"] = module
                await self.store.put("gone", getattr(module, "Gone")(), None)

                if removal == "module":
                    del sys.modules["cache_fixture_models"]
                else:
                    delattr(module, "Gone")

                self.assertIs(await self.store.get("gone"), MISSING)
                self.assertEqual(self.files(), [])

    async def test_forget_reports_whether_key_existed(self):
        await self.store.put("name", "taylor", None)

        self.assertIs(await self.store.forget("name"), True)
        self.assertIs(await self.store.forget("name"), False)
        self.assertIs(await self.store.get("name"), MISSING)

    async def test_flush_removes_cache_shards_only(self):
        await self.store.put("a", 1, None)
        await self.store.put("b", 2, None)
        (self.directory / ".gitignore").write_text("*\n")
        (self.directory / "keep").mkdir()

        self.assertIs(await self.store.flush(), True)

        self.assertIs(await self.store.get("a"), MISSING)
        self.assertIs(await self.store.get("b"), MISSING)
        self.assertEqual(sorted(path.name for path in self.directory.iterdir()), [".gitignore", "keep"])

    async def test_flush_without_directory(self):
        self.assertIs(await FileStore(self.root / "absent").flush(), True)
