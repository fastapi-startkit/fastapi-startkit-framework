import hashlib
import os
import pickle
import sys
import types
from dataclasses import dataclass

import pytest

from fastapi_startkit.cache import MISSING, FileStore


@dataclass
class User:
    name: str


@pytest.fixture
def directory(tmp_path):
    return tmp_path / "cache"


@pytest.fixture
def store(directory):
    return FileStore(directory)


def files(directory):
    return sorted(path.name for path in directory.rglob("*") if path.is_file())


async def test_missing_key_returns_sentinel(store):
    assert await store.get("name") is MISSING


async def test_round_trips_python_objects(store):
    assert await store.put("user", User("taylor"), 60) is True

    assert await store.get("user") == User("taylor")


async def test_layout_uses_sharded_sha1_paths(store, directory):
    await store.put("name", "taylor", None)
    digest = hashlib.sha1(b"name").hexdigest()

    path = directory / digest[:2] / digest[2:4] / digest
    assert path.is_file()
    assert pickle.loads(path.read_bytes()) == (None, "taylor")


async def test_cached_none_is_a_hit(store):
    await store.put("nothing", None, None)

    assert await store.get("nothing") is None


async def test_entry_expires_and_file_is_removed(store, directory, clock):
    await store.put("name", "taylor", 10)

    clock.travel(9)
    assert await store.get("name") == "taylor"

    clock.travel(1)
    assert await store.get("name") is MISSING
    assert files(directory) == []


async def test_forever_never_expires(store, clock):
    await store.put("name", "taylor", None)

    clock.travel(10**9)

    assert await store.get("name") == "taylor"


async def test_put_overwrites(store):
    await store.put("name", "taylor", None)
    await store.put("name", "otwell", None)

    assert await store.get("name") == "otwell"


async def test_write_is_atomic_and_leaves_no_temporary_file(store, directory, monkeypatch):
    await store.put("name", "taylor", None)

    def failing_replace(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError, match="disk full"):
        await store.put("name", "otwell", None)

    monkeypatch.undo()
    assert await store.get("name") == "taylor"
    assert len(files(directory)) == 1


async def test_unpicklable_value_raises_without_writing(store, directory):
    with pytest.raises((pickle.PicklingError, TypeError, AttributeError)):
        await store.put("lambda", lambda: 1, None)

    assert files(directory) == []


async def test_corrupt_file_is_a_miss_and_removed(store, directory):
    await store.put("name", "taylor", None)
    store.path("name").write_bytes(b"not a pickle")

    assert await store.get("name") is MISSING
    assert files(directory) == []


@pytest.mark.parametrize("removal", ["module", "class"])
async def test_value_of_removed_class_is_a_miss_and_removed(store, directory, monkeypatch, removal):
    module = types.ModuleType("cache_fixture_models")
    module.Gone = type("Gone", (), {"__module__": "cache_fixture_models"})
    monkeypatch.setitem(sys.modules, "cache_fixture_models", module)
    await store.put("gone", module.Gone(), None)

    if removal == "module":
        monkeypatch.delitem(sys.modules, "cache_fixture_models")
    else:
        monkeypatch.delattr(module, "Gone")

    assert await store.get("gone") is MISSING
    assert files(directory) == []


async def test_forget_reports_whether_key_existed(store):
    await store.put("name", "taylor", None)

    assert await store.forget("name") is True
    assert await store.forget("name") is False
    assert await store.get("name") is MISSING


async def test_flush_removes_cache_shards_only(store, directory):
    await store.put("a", 1, None)
    await store.put("b", 2, None)
    (directory / ".gitignore").write_text("*\n")
    (directory / "keep").mkdir()

    assert await store.flush() is True

    assert await store.get("a") is MISSING
    assert await store.get("b") is MISSING
    assert sorted(path.name for path in directory.iterdir()) == [".gitignore", "keep"]


async def test_flush_without_directory(tmp_path):
    assert await FileStore(tmp_path / "absent").flush() is True
