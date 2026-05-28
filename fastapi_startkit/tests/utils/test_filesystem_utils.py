"""Tests for filesystem utility functions (task #15)."""

import os


from fastapi_startkit.utils.filesystem import (
    file_exists,
    get_extension,
    make_directory,
    make_full_directory,
    modified_date,
)


class TestMakeDirectory:
    def test_creates_parent_directories(self, tmp_path):
        target = str(tmp_path / "sub" / "dir" / "file.txt")
        make_directory(target)
        assert os.path.exists(str(tmp_path / "sub" / "dir"))

    def test_returns_true_when_created(self, tmp_path):
        target = str(tmp_path / "newdir" / "file.txt")
        result = make_directory(target)
        assert result is True

    def test_returns_false_for_existing_file(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("data")
        result = make_directory(str(f))
        assert result is False


class TestMakeFullDirectory:
    def test_creates_full_directory_tree(self, tmp_path):
        target = str(tmp_path / "a" / "b" / "c")
        make_full_directory(target)
        assert os.path.exists(target)

    def test_returns_true_when_created(self, tmp_path):
        target = str(tmp_path / "fresh_dir")
        result = make_full_directory(target)
        assert result is True

    def test_existing_directory_returns_true(self, tmp_path):
        result = make_full_directory(str(tmp_path))
        assert result is True

    def test_returns_false_for_existing_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        result = make_full_directory(str(f))
        assert result is False


class TestFileExists:
    def test_returns_true_for_existing_directory(self, tmp_path):
        f = tmp_path / "sub" / "file.txt"
        f.parent.mkdir(parents=True)
        assert file_exists(str(f)) is True

    def test_returns_false_for_nonexistent_directory(self, tmp_path):
        f = tmp_path / "no_such_dir" / "file.txt"
        assert file_exists(str(f)) is False


class TestModifiedDate:
    def test_returns_numeric_timestamp(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        ts = modified_date(str(f))
        assert isinstance(ts, float)
        assert ts > 0


class TestGetExtension:
    def test_simple_extension(self):
        assert get_extension("file.txt") == ".txt"

    def test_no_extension(self):
        assert get_extension("noextension") == ""

    def test_hidden_file_no_content_extension(self):
        # .hidden files (no secondary extension) return ""
        result = get_extension(".hidden")
        assert result == ""

    def test_double_extension_tar_gz(self):
        result = get_extension("archive.tar.gz")
        assert result == ".tar.gz"

    def test_image_extensions(self):
        assert get_extension("photo.jpg") == ".jpg"
        assert get_extension("graphic.png") == ".png"

    def test_without_dot(self):
        result = get_extension("file.txt", without_dot=True)
        assert result == "txt"

    def test_path_with_directory(self):
        assert get_extension("/some/path/to/file.py") == ".py"
