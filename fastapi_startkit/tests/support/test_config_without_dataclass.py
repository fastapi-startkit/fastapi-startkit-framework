import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, fields
from threading import Barrier

import fastapi_startkit.support.config as config_module
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


def test_decorated_child_inherits_undecorated_parent_fields(monkeypatch):
    class Parent(Config):
        host: str = env("PLAIN_PARENT_HOST", "localhost")

    @dataclass
    class Child(Parent):
        port: int = env("PLAIN_CHILD_PORT", 80)

    monkeypatch.setenv("PLAIN_PARENT_HOST", "example.test")
    assert [field.name for field in fields(Child)] == ["host", "port"]
    assert (Child().host, Child().port) == ("example.test", 80)
    assert Child.host == "example.test"


def test_config_base_is_never_a_dataclass():
    class Plain(Config):
        host: str = env("PLAIN_BASE_HOST", "localhost")

    Plain()
    Config()
    assert "__dataclass_fields__" not in Config.__dict__
    assert Config.__hash__ is object.__hash__
    first, second = Config(), Config()
    assert first != second
    assert hash(first) != hash(second)


def test_undecorated_subclass_instances_stay_hashable():
    class Hashable(Config):
        host: str = env("PLAIN_HASH_HOST", "localhost")

    first, second = Hashable(), Hashable()
    assert len({first, second, Config()}) == 3
    assert first != second


def test_environment_is_read_on_every_instantiation(monkeypatch):
    class Live(Config):
        connections: dict[str, str] = field(default_factory=lambda: {"default": "sqlite"})
        host: str = env("PLAIN_LIVE_HOST", "localhost")

    monkeypatch.setenv("PLAIN_LIVE_HOST", "first")
    first = Live()
    monkeypatch.setenv("PLAIN_LIVE_HOST", "second")
    second = Live()
    assert (first.host, second.host) == ("first", "second")
    assert first.connections is not second.connections


def test_concurrent_first_instantiation_decorates_once(monkeypatch):
    class Concurrent(Config):
        connections: dict[str, str] = field(default_factory=lambda: {"default": "sqlite"})
        host: str = env("PLAIN_CONCURRENT_HOST", "localhost")

    calls: list[type] = []
    original = config_module.dataclass

    def counting_dataclass(**options: bool):
        def decorate(klass: type) -> type:
            calls.append(klass)
            time.sleep(0.01)
            return original(**options)(klass)

        return decorate

    monkeypatch.setattr(config_module, "dataclass", counting_dataclass)
    barrier = Barrier(8)

    def build(_: int) -> Concurrent:
        barrier.wait()
        return Concurrent()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(build, range(8)))

    assert calls == [Concurrent]
    assert all(result.host == "localhost" for result in results)
