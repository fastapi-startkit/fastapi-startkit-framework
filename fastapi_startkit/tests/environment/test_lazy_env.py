from dataclasses import dataclass, field
from typing import assert_type
from unittest.mock import patch

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.environment import env, value
from fastapi_startkit.masoniteorm import DatabaseConfig, MySQLConfig
from fastapi_startkit.masoniteorm.providers import DatabaseProvider


def test_env_reads_only_when_resolved():
    with patch("fastapi_startkit.environment.environment.os.getenv", return_value="6379") as getenv:
        resolver = env("LAZY_TEST_PORT", 1)
        getenv.assert_not_called()
        assert_type(resolver, int)
        assert_type(value(resolver), int)
        assert value(resolver) == 6379
        getenv.assert_called_with("LAZY_TEST_PORT", 1)


def test_resolver_reads_current_environment(monkeypatch):
    resolver = env("LAZY_TEST_VALUE", "fallback")
    monkeypatch.setenv("LAZY_TEST_VALUE", "first")
    assert value(resolver) == "first"
    monkeypatch.setenv("LAZY_TEST_VALUE", "second")
    assert value(resolver) == "second"


@pytest.mark.parametrize("item", [None, False, 0, "00123", {"key": "value"}])
def test_value_preserves_plain_values(item):
    assert value(item) is item


def test_value_preserves_callables():
    assert value(len) is len


def test_field_defaults_are_independent():
    calls = []

    def items():
        calls.append(True)
        return {"values": []}

    @dataclass
    class Settings:
        options: dict = field(default_factory=items)

    assert calls == []
    first = Settings()
    second = Settings()
    assert len(calls) == 2
    first.options["values"].append("first")
    assert second.options == {"values": []}
    assert Settings(options={"override": True}).options == {"override": True}
    assert len(calls) == 2


def test_direct_dataclass_environment_fields(monkeypatch):
    @dataclass
    class Settings:
        port: int = env("LAZY_TEST_PORT", 5432)
        host: str = env("LAZY_TEST_HOST", "localhost")

    monkeypatch.setenv("LAZY_TEST_PORT", "6379")
    settings = Settings()
    assert_type(settings.port, int)
    assert_type(settings.host, str)
    assert settings.port == 6379
    assert Settings(port=3306).port == 3306
    monkeypatch.setenv("LAZY_TEST_PORT", "5433")
    assert Settings().port == 5433
    assert settings.port == 6379


def test_explicit_factory_remains_supported(monkeypatch):
    @dataclass
    class Settings:
        port: int = field(default_factory=lambda: value(env("LAZY_TEST_PORT", 5432)))

    monkeypatch.setenv("LAZY_TEST_PORT", "6379")
    assert Settings().port == 6379


def test_inherited_environment_fields(monkeypatch):
    @dataclass
    class BaseSettings:
        port: int = env("LAZY_TEST_PORT", 5432)

    @dataclass
    class Settings(BaseSettings):
        host: str = env("LAZY_TEST_HOST", "localhost")

    monkeypatch.setenv("LAZY_TEST_PORT", "6379")
    assert Settings().port == 6379
    assert Settings(host="db").host == "db"


def test_resolver_propagates_errors(monkeypatch):
    resolver = env("LAZY_TEST_PORT", 1)
    monkeypatch.setenv("LAZY_TEST_PORT", "invalid")
    with pytest.raises(ValueError, match="LAZY_TEST_PORT"):
        value(resolver)


def test_database_config_reads_environment_on_first_access(monkeypatch):
    monkeypatch.setenv("DB_HOST", "first")
    monkeypatch.setenv("DB_PORT", "3307")
    monkeypatch.setenv("DB_PASSWORD", "00123")
    first = MySQLConfig()
    assert first.host == "first"
    monkeypatch.setenv("DB_HOST", "second")
    second = MySQLConfig()
    assert first.host == "first"
    assert second.host == "second"
    assert second.port == 3307
    assert second.password == "00123"


def test_application_loads_environment_before_database_settings(tmp_path, monkeypatch):
    for key in ("DB_CONNECTION", "DB_DATABASE", "DB_ECHO"):
        monkeypatch.setenv(key, "")
    (tmp_path / ".env").write_text("DB_CONNECTION=sqlite\nDB_DATABASE=loaded.sqlite\nDB_ECHO=true\n")
    application = Application(base_path=tmp_path, providers=[(DatabaseProvider, DatabaseConfig)])
    config = application.make("db").config
    assert config.default == "sqlite"
    assert config.connections["sqlite"].database == "loaded.sqlite"
    assert config.connections["sqlite"].echo is True
