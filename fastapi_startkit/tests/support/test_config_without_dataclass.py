from dataclasses import dataclass, fields

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


class PlainDatabaseConfig(Config):
    default: str = env("PLAIN_DB_CONNECTION", "sqlite")
    port: int = env("PLAIN_DB_PORT", 5432)
    debug: bool = env("PLAIN_DB_DEBUG", False)


def test_fallback_is_returned_when_variable_is_unset(monkeypatch):
    monkeypatch.delenv("PLAIN_DB_CONNECTION", raising=False)
    assert PlainDatabaseConfig().default == "sqlite"


def test_variable_value_is_returned_when_set(monkeypatch):
    monkeypatch.setenv("PLAIN_DB_CONNECTION", "pgsql")
    assert PlainDatabaseConfig().default == "pgsql"


def test_values_are_cast_to_default_type(monkeypatch):
    monkeypatch.setenv("PLAIN_DB_PORT", "6543")
    monkeypatch.setenv("PLAIN_DB_DEBUG", "true")
    config = PlainDatabaseConfig()
    assert config.port == 6543
    assert config.debug is True


def test_keyword_arguments_override_environment(monkeypatch):
    monkeypatch.setenv("PLAIN_DB_CONNECTION", "pgsql")
    assert PlainDatabaseConfig(default="mysql").default == "mysql"


def test_undecorated_parent_fields_are_inherited(monkeypatch):
    class Parent(Config):
        host: str = env("PLAIN_PARENT_HOST", "localhost")

    class Child(Parent):
        port: int = env("PLAIN_CHILD_PORT", 80)

    monkeypatch.setenv("PLAIN_PARENT_HOST", "example.test")
    child = Child()
    assert (child.host, child.port) == ("example.test", 80)
    assert Parent().host == "example.test"


def test_decorated_class_is_not_processed_again(monkeypatch):
    @dataclass
    class Decorated(Config):
        host: str = env("PLAIN_DECORATED_HOST", "localhost")

    original = Decorated.__dataclass_fields__
    monkeypatch.setenv("PLAIN_DECORATED_HOST", "example.test")
    assert Decorated().host == "example.test"
    assert Decorated.__dataclass_fields__ is original
    assert [field.name for field in fields(Decorated)] == ["host"]
