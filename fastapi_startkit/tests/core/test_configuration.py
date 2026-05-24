"""Tests for the Configuration system (task #8)."""

import pytest

from fastapi_startkit.configuration.config import Config
from fastapi_startkit.configuration.helpers import config
from fastapi_startkit.container.container import Container
from fastapi_startkit.environment.environment import env


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container_instance():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    from fastapi_startkit.application import Application

    return Application(base_path=tmp_path, env="testing")


@pytest.fixture
def configuration(app):
    return app.make("config")


# ---------------------------------------------------------------------------
# env() helper
# ---------------------------------------------------------------------------


class TestEnvHelper:
    def test_returns_string_value(self, monkeypatch):
        monkeypatch.setenv("TEST_STR", "hello")
        assert env("TEST_STR") == "hello"

    def test_returns_default_when_missing(self):
        assert env("DOES_NOT_EXIST_XYZ", "fallback") == "fallback"

    def test_casts_integer(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "42")
        assert env("TEST_INT") == 42
        assert isinstance(env("TEST_INT"), int)

    def test_casts_true_string(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_T", "true")
        assert env("TEST_BOOL_T") is True

    def test_casts_false_string(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_F", "false")
        assert env("TEST_BOOL_F") is False

    def test_casts_True_capitalised(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_TC", "True")
        assert env("TEST_BOOL_TC") is True

    def test_casts_False_capitalised(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_FC", "False")
        assert env("TEST_BOOL_FC") is False

    def test_no_cast_returns_raw_string(self, monkeypatch):
        monkeypatch.setenv("TEST_RAW", "42")
        assert env("TEST_RAW", cast=False) == "42"

    def test_returns_none_when_value_is_none_default(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        assert env("NONEXISTENT_VAR", None) is None

    def test_empty_string_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        result = env("EMPTY_VAR", "default_val")
        assert result == "default_val"


# ---------------------------------------------------------------------------
# Configuration.set / get / has / all
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_set_and_get_simple_value(self, configuration):
        configuration.set("mykey", "myvalue")
        assert configuration.get("mykey") == "myvalue"

    def test_get_returns_default_for_missing_key(self, configuration):
        assert configuration.get("does_not_exist") is None
        assert configuration.get("does_not_exist", "default") == "default"

    def test_has_returns_true_for_existing_key(self, configuration):
        configuration.set("exists", 1)
        assert configuration.has("exists") is True

    def test_has_returns_false_for_missing_key(self, configuration):
        assert configuration.has("not_here") is False

    def test_all_returns_full_dict(self, configuration):
        configuration.set("a", 1)
        configuration.set("b", 2)
        result = configuration.all()
        assert result["a"] == 1
        assert result["b"] == 2

    def test_set_dict_value(self, configuration):
        configuration.set("db", {"host": "localhost", "port": 5432})
        db = configuration.get("db")
        assert db["host"] == "localhost"
        assert db["port"] == 5432

    def test_overwrite_key(self, configuration):
        configuration.set("key", "first")
        configuration.set("key", "second")
        assert configuration.get("key") == "second"


# ---------------------------------------------------------------------------
# Configuration.merge_with
# ---------------------------------------------------------------------------


class TestMergeWith:
    def test_merge_adds_new_keys_from_external(self, configuration):
        # No existing "redis" key — external dict becomes the base
        configuration.merge_with("redis", {"HOST": "redis.example.com", "PORT": "6379"})
        result = configuration.get("redis")
        assert result["host"] == "redis.example.com"

    def test_existing_values_win_over_external(self, configuration):
        # Existing config takes priority over external (provider default pattern)
        configuration.set("cache", {"driver": "memory", "ttl": 300})
        configuration.merge_with("cache", {"DRIVER": "redis", "TTL": "60"})
        result = configuration.get("cache")
        assert result["driver"] == "memory"  # existing wins
        assert result["ttl"] == 300  # existing wins

    def test_merge_with_adds_missing_keys(self, configuration):
        # Keys not in existing config are added from external
        configuration.set("mail", {"from": "app@example.com"})
        configuration.merge_with("mail", {"DRIVER": "smtp"})
        result = configuration.get("mail")
        assert result["driver"] == "smtp"  # new key added
        assert result["from"] == "app@example.com"  # existing preserved

    def test_merge_with_non_reserved_key_works(self, configuration):
        configuration.merge_with("custom_key", {"FOO": "bar"})
        assert configuration.get("custom_key")["foo"] == "bar"


# ---------------------------------------------------------------------------
# Config static facade (requires booted app)
# ---------------------------------------------------------------------------


class TestConfigStaticClass:
    def test_config_get_returns_value(self, app):
        app.make("config").set("app.name", "MyApp")
        assert Config.get("app.name") == "MyApp"

    def test_config_set_stores_value(self, app):
        Config.set("app.debug", True)
        assert Config.get("app.debug") is True

    def test_config_has_existing_key(self, app):
        Config.set("app.env", "testing")
        assert Config.has("app.env") is True

    def test_config_has_missing_key(self, app):
        assert Config.has("nonexistent.key") is False

    def test_config_get_default(self, app):
        assert Config.get("missing.key", "fallback") == "fallback"

    def test_config_all_returns_mapping(self, app):
        Config.set("x", 99)
        result = Config.all()
        # all() returns a dotty-dict mapping, supports key access
        assert result["x"] == 99


# ---------------------------------------------------------------------------
# config() helper function (configuration/helpers.py)
# ---------------------------------------------------------------------------


class TestConfigHelperFunction:
    def test_config_helper_delegates_to_Config(self, app):
        Config.set("site.title", "FastAPI Startkit")
        assert config("site.title") == "FastAPI Startkit"

    def test_config_helper_returns_default(self, app):
        assert config("missing.path", "def") == "def"
