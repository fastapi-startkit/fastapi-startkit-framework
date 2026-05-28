"""Tests for the LocalDriver, FakeDriver, and FileStream (task #14)."""

import os
from unittest.mock import MagicMock

import pytest

from fastapi_startkit.storage.drivers.fake import FakeDriver
from fastapi_startkit.storage.drivers.local import LocalDriver
from fastapi_startkit.storage.filestream import FileStream


# ---------------------------------------------------------------------------
# LocalDriver — put / get / delete / exists / list / move / copy
# ---------------------------------------------------------------------------


class TestLocalDriverPutGet:
    @pytest.fixture
    def driver(self, tmp_path):
        app = MagicMock()
        app.base_path = str(tmp_path)
        d = LocalDriver(app)
        d.set_options({"root": str(tmp_path / "storage")})
        return d

    def test_put_creates_file(self, driver, tmp_path):
        driver.put("hello.txt", "hello world")
        path = tmp_path / "storage" / "hello.txt"
        assert path.exists()
        assert path.read_text() == "hello world"

    def test_put_binary_content(self, driver, tmp_path):
        driver.put("data.bin", b"\x00\x01\x02")
        path = tmp_path / "storage" / "data.bin"
        assert path.read_bytes() == b"\x00\x01\x02"

    def test_get_returns_content(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        (tmp_path / "storage" / "read.txt").write_text("read me")
        assert driver.get("read.txt") == "read me"

    def test_get_returns_none_for_missing_file(self, driver):
        result = driver.get("nonexistent.txt")
        assert result is None

    def test_exists_true_for_present_file(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        (tmp_path / "storage" / "present.txt").write_text("here")
        assert driver.exists("present.txt") is True

    def test_exists_false_for_missing_file(self, driver):
        assert driver.exists("missing.txt") is False

    def test_missing_is_inverse_of_exists(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        (tmp_path / "storage" / "file.txt").write_text("x")
        assert driver.missing("file.txt") is False
        assert driver.missing("no_file.txt") is True

    def test_delete_removes_file(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        target = tmp_path / "storage" / "delete_me.txt"
        target.write_text("bye")
        driver.delete("delete_me.txt")
        assert not target.exists()

    def test_append_adds_to_existing_content(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        (tmp_path / "storage" / "log.txt").write_text("line1\n")
        driver.append("log.txt", "line2\n")
        assert (tmp_path / "storage" / "log.txt").read_text() == "line1\nline2\n"

    def test_prepend_adds_before_existing_content(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        (tmp_path / "storage" / "pre.txt").write_text("world")
        driver.prepend("pre.txt", "hello ")
        assert (tmp_path / "storage" / "pre.txt").read_text() == "hello world"

    def test_move_relocates_file(self, driver, tmp_path):
        (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
        src = tmp_path / "storage" / "src.txt"
        src.write_text("move me")
        driver.move("src.txt", "dst.txt")
        assert not src.exists()
        assert (tmp_path / "storage" / "dst.txt").read_text() == "move me"

    def test_copy_duplicates_file(self, driver, tmp_path):
        storage = tmp_path / "storage"
        storage.mkdir(parents=True, exist_ok=True)
        src = storage / "orig.txt"
        src.write_text("copy me")
        driver.copy(str(src), str(storage / "copy.txt"))
        assert src.exists()
        assert (storage / "copy.txt").read_text() == "copy me"

    def test_get_files_lists_files_in_directory(self, driver, tmp_path):
        storage = tmp_path / "storage"
        storage.mkdir(parents=True, exist_ok=True)
        (storage / "a.txt").write_text("a")
        (storage / "b.txt").write_text("b")
        files = driver.get_files("")
        names = [f.name() for f in files]
        assert set(names) == {"a.txt", "b.txt"}


# ---------------------------------------------------------------------------
# FakeDriver — in-memory / temp directory behaviour
# ---------------------------------------------------------------------------


class TestFakeDriver:
    @pytest.fixture
    def fake(self):
        app = MagicMock()
        app.base_path = "/fake"
        return FakeDriver(app, disk_name="test")

    def test_fake_driver_uses_temp_directory(self, fake):
        assert os.path.exists(fake._root)
        assert "storage_fake_test_" in fake._root

    def test_fake_driver_put_and_assert_exists(self, fake):
        fake.put("hello.txt", "hi")
        fake.assert_exists("hello.txt")

    def test_fake_driver_assert_exists_with_content(self, fake):
        fake.put("content.txt", "expected")
        fake.assert_exists("content.txt", content="expected")

    def test_fake_driver_assert_missing(self, fake):
        fake.assert_missing("gone.txt")

    def test_fake_driver_assert_missing_after_delete(self, fake):
        fake.put("temp.txt", "x")
        fake.delete("temp.txt")
        fake.assert_missing("temp.txt")

    def test_fake_driver_assert_count(self, fake):
        fake.put("one.txt", "1")
        fake.put("two.txt", "2")
        fake.assert_count(2)

    def test_fake_driver_assert_directory_empty(self, fake):
        fake.assert_directory_empty()

    def test_fake_driver_set_options_is_noop(self, fake):
        original_root = fake._root
        fake.set_options({"root": "/different/path"})
        assert fake.options["root"] == original_root

    def test_fake_driver_cleanup_removes_directory(self, fake):
        root = fake._root
        assert os.path.exists(root)
        fake.cleanup()
        assert not os.path.exists(root)

    def test_fake_driver_context_manager(self):
        app = MagicMock()
        app.base_path = "/fake"
        with FakeDriver(app, disk_name="ctx") as fake:
            fake.put("file.txt", "data")
            fake.assert_exists("file.txt")
            root = fake._root
        assert not os.path.exists(root)

    def test_fake_driver_isolated_between_instances(self):
        app = MagicMock()
        app.base_path = "/fake"
        fake1 = FakeDriver(app, disk_name="iso")
        fake2 = FakeDriver(app, disk_name="iso")
        fake1.put("shared.txt", "in fake1")
        fake2.assert_missing("shared.txt")
        fake1.cleanup()
        fake2.cleanup()


# ---------------------------------------------------------------------------
# FileStream
# ---------------------------------------------------------------------------


class TestFileStream:
    def test_filestream_path(self, tmp_path):
        f = tmp_path / "sample.txt"
        f.write_text("hello")
        with open(f) as fh:
            stream = FileStream(fh)
            assert stream.path() == str(f)

    def test_filestream_extension(self, tmp_path):
        f = tmp_path / "image.png"
        f.write_text("data")
        with open(f) as fh:
            stream = FileStream(fh)
            assert stream.extension() == ".png"

    def test_filestream_name_from_path(self, tmp_path):
        f = tmp_path / "document.pdf"
        f.write_text("pdf")
        with open(f) as fh:
            stream = FileStream(fh)
            assert stream.name() == "document.pdf"

    def test_filestream_name_from_explicit_name(self, tmp_path):
        f = tmp_path / "actual.txt"
        f.write_text("text")
        with open(f) as fh:
            stream = FileStream(fh, name="alias.txt")
            assert stream.name() == "alias.txt"

    def test_filestream_extension_from_explicit_name(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("text")
        with open(f) as fh:
            stream = FileStream(fh, name="renamed.csv")
            assert stream.extension() == ".csv"
