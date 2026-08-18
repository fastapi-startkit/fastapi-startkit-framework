"""Unit tests for the data-structure helpers in support/structures.py (task #1214)."""

import pytest
from dotty_dict import Dotty

from fastapi_startkit.exceptions.exceptions import LoaderNotFound
from fastapi_startkit.support.structures import data, data_get, data_set, load


class TestData:
    def test_wraps_dict_in_dotty(self):
        result = data({"a": {"b": 1}})
        assert isinstance(result, Dotty)
        assert result["a.b"] == 1

    def test_none_yields_empty_dotty(self):
        result = data(None)
        assert isinstance(result, Dotty)
        assert result.to_dict() == {}


class TestDataGet:
    def test_reads_nested_value(self):
        assert data_get({"app": {"name": "startkit"}}, "app.name") == "startkit"

    def test_missing_key_returns_default(self):
        assert data_get({"app": {}}, "app.missing", "fallback") == "fallback"

    def test_wildcard_collects_matches_across_a_list(self):
        source = {"users": [{"name": "ann"}, {"name": "bob"}]}
        assert data_get(source, "users.*.name") == ["ann", "bob"]


class TestDataSet:
    def test_sets_nested_value_and_returns_same_dict(self):
        target = {"app": {}}
        result = data_set(target, "app.name", "startkit")
        assert result is target
        assert target["app"]["name"] == "startkit"

    def test_overwrites_by_default(self):
        target = {"app": {"name": "old"}}
        data_set(target, "app.name", "new")
        assert target["app"]["name"] == "new"

    def test_no_overwrite_keeps_existing_value(self):
        target = {"app": {"name": "old"}}
        result = data_set(target, "app.name", "new", overwrite=False)
        assert result is None
        assert target["app"]["name"] == "old"

    def test_wildcard_key_raises(self):
        with pytest.raises(ValueError):
            data_set({}, "users.*.name", "x")


class TestLoad:
    def _write_module(self, tmp_path):
        module = tmp_path / "sample_module.py"
        module.write_text("VALUE = 42\n\n\ndef greet():\n    return 'hi'\n")
        return str(module)

    def test_loads_whole_module(self, tmp_path):
        path = self._write_module(tmp_path)
        module = load(path)
        assert module.VALUE == 42
        assert module.greet() == "hi"

    def test_loads_named_object(self, tmp_path):
        path = self._write_module(tmp_path)
        assert load(path, "VALUE") == 42

    def test_missing_object_raises_attribute_error(self, tmp_path):
        path = self._write_module(tmp_path)
        with pytest.raises(AttributeError):
            load(path, "MISSING", default="fallback")

    def test_bad_path_returns_none(self):
        assert load("/no/such/module.py") is None

    def test_bad_path_raises_when_requested(self):
        with pytest.raises(LoaderNotFound):
            load("/no/such/module.py", raise_exception=True)
