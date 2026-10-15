from dataclasses import dataclass

import pytest

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm.config.database import DatabaseConfig


def test_class_defaults_read_current_environment(monkeypatch):
    monkeypatch.setenv("DB_CONNECTION", "sqlite")
    instance = DatabaseConfig(default="custom")
    assert DatabaseConfig.default == "sqlite"
    monkeypatch.setenv("DB_CONNECTION", "mysql")
    assert DatabaseConfig.default == "mysql"
    assert instance.default == "custom"


def test_class_collections_are_independent(monkeypatch):
    monkeypatch.setenv("DB_DATABASE", "first.sqlite")
    first = DatabaseConfig.connections
    assert first["sqlite"].database == "first.sqlite"
    monkeypatch.setenv("DB_DATABASE", "second.sqlite")
    second = DatabaseConfig.connections
    assert first["sqlite"].database == "first.sqlite"
    assert second["sqlite"].database == "second.sqlite"
    assert first is not second
    first.clear()
    assert "sqlite" in DatabaseConfig.connections


def test_subclass_defaults(monkeypatch):
    @dataclass
    class CustomConfig(DatabaseConfig):
        default: str = env("CUSTOM_DB", "sqlite")

    monkeypatch.setenv("CUSTOM_DB", "custom")
    assert CustomConfig.default == "custom"
    assert CustomConfig().default == "custom"
    assert CustomConfig(default="explicit").default == "explicit"
    assert "sqlite" in CustomConfig.connections


def test_required_and_unknown_fields_raise_attribute_error():
    @dataclass
    class RequiredConfig(Config):
        required: str
        plain: str = "default"

    assert RequiredConfig.plain == "default"
    assert RequiredConfig(required="value").required == "value"
    for target, name in [(RequiredConfig, "required"), (DatabaseConfig, "missing"), (Config, "missing")]:
        with pytest.raises(AttributeError, match=name):
            getattr(target, name)
