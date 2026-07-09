"""Tests for the data-structure helpers (task #722).

Covers ``load`` (module/attribute loading and failure handling) and the dotted
dictionary helpers ``data``, ``data_get`` and ``data_set``. Modules are loaded
from files written under pytest's ``tmp_path`` so no fixtures live on disk.
"""

import pytest
from dotty_dict import Dotty

from fastapi_startkit.exceptions.exceptions import LoaderNotFound
from fastapi_startkit.utils.structures import data, data_get, data_set, load

MODULE_SOURCE = "VALUE = 42\n\n\ndef greet():\n    return 'hi'\n"


def _write_module(tmp_path, name="sample.py", source=MODULE_SOURCE):
    path = tmp_path / name
    path.write_text(source)
    return str(path)


class TestLoad:
    def test_returns_module_when_no_object_name(self, tmp_path):
        module = load(_write_module(tmp_path))
        assert module.VALUE == 42

    def test_returns_named_attribute(self, tmp_path):
        path = _write_module(tmp_path)
        assert load(path, "VALUE") == 42
        assert load(path, "greet")() == "hi"

    def test_bad_path_returns_none(self, tmp_path, capsys):
        result = load(str(tmp_path / "missing.py"))
        assert result is None
        assert "error when loading from file" in capsys.readouterr().out

    def test_bad_path_raises_when_requested(self, tmp_path):
        with pytest.raises(LoaderNotFound):
            load(str(tmp_path / "missing.py"), raise_exception=True)

    def test_dotted_path_without_slash(self, tmp_path):
        # No "/" in the name triggers the ``.replace('.py', '')`` branch.
        result = load("definitely_not_a_real_module")
        assert result is None


class TestData:
    def test_returns_dotty(self):
        assert isinstance(data({"a": 1}), Dotty)

    def test_defaults_to_empty(self):
        assert dict(data()) == {}


class TestDataGet:
    def test_reads_nested_value(self):
        assert data_get({"a": {"b": 1}}, "a.b") == 1

    def test_returns_default_for_missing_key(self):
        assert data_get({"a": {}}, "a.missing", "fallback") == "fallback"

    def test_wildcard_is_translated(self):
        # A "*" in the key is rewritten to dotty's ":" wildcard; the lookup
        # runs without raising and falls back to the default when unmatched.
        assert data_get({"a": {"b": 2}}, "a.*", "fallback") == "fallback"


class TestDataSet:
    def test_sets_value_under_existing_parent(self):
        source = {"a": {"b": 1}}
        result = data_set(source, "a.c", 7)
        assert result is source
        assert source["a"]["c"] == 7

    def test_does_not_overwrite_when_disabled(self):
        source = {"a": {"b": 1}}
        assert data_set(source, "a.b", 9, overwrite=False) is None
        assert source["a"]["b"] == 1

    def test_overwrites_by_default(self):
        source = {"a": {"b": 1}}
        data_set(source, "a.b", 9)
        assert source["a"]["b"] == 9

    def test_wildcard_key_raises(self):
        with pytest.raises(ValueError):
            data_set({}, "a.*", 1)
