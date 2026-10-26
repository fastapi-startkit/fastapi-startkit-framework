from dataclasses import FrozenInstanceError, dataclass, field, fields, is_dataclass

import pytest

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env
from fastapi_startkit.storage.storage import StorageManager
from fastapi_startkit.support.dataclass import Dataclass


def test_reported_database_config_without_dataclass(monkeypatch):
    class DatabaseConfig(Config):
        default: str = env("DB_CONNECTION", "sqlite")

    monkeypatch.delenv("DB_CONNECTION", raising=False)
    assert DatabaseConfig().default == "sqlite"
    monkeypatch.setenv("DB_CONNECTION", "mysql")
    assert DatabaseConfig().default == "mysql"


class PlainDatabaseConfig(Config):
    default: str = env("PLAIN_DB_CONNECTION", "sqlite")
    port: int = env("PLAIN_DB_PORT", 5432)
    debug: bool = env("PLAIN_DB_DEBUG", False)


def test_subclass_is_a_dataclass_at_definition():
    class Defined(Config):
        host: str = env("PLAIN_DEFINED_HOST", "localhost")

    assert "__dataclass_fields__" in Defined.__dict__
    assert [declared.name for declared in fields(Defined)] == ["host"]


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
    assert Child.host == "example.test"


def test_explicit_dataclass_reprocessing_keeps_env_live(monkeypatch):
    @dataclass
    class Decorated(Config):
        host: str = env("PLAIN_DECORATED_HOST", "localhost")
        connections: dict[str, str] = field(default_factory=lambda: {"default": "sqlite"})

    monkeypatch.setenv("PLAIN_DECORATED_HOST", "example.test")
    assert [declared.name for declared in fields(Decorated)] == ["host", "connections"]
    assert Decorated.host == "example.test"
    assert Decorated().host == "example.test"
    assert Decorated().connections is not Decorated().connections


def test_explicit_dataclass_options_replace_automatic_ones():
    @dataclass(frozen=True, kw_only=True)
    class Decorated(Config):
        host: str = env("PLAIN_OPTIONS_HOST", "localhost")

    config = Decorated(host="example.test")
    assert config == Decorated(host="example.test")
    with pytest.raises(TypeError):
        Decorated("positional")
    with pytest.raises(FrozenInstanceError):
        config.host = "changed"


def test_decorated_child_inherits_undecorated_parent_fields(monkeypatch):
    class Parent(Config):
        host: str = env("PLAIN_PARENT_HOST", "localhost")

    @dataclass
    class Child(Parent):
        port: int = env("PLAIN_CHILD_PORT", 80)

    monkeypatch.setenv("PLAIN_PARENT_HOST", "example.test")
    assert [declared.name for declared in fields(Child)] == ["host", "port"]
    assert (Child().host, Child().port) == ("example.test", 80)
    assert Child.host == "example.test"


def test_config_base_is_never_a_dataclass():
    class Plain(Config):
        host: str = env("PLAIN_BASE_HOST", "localhost")

    Plain()
    assert not is_dataclass(Config)
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


def test_undecorated_child_of_frozen_parent_is_frozen():
    @dataclass(frozen=True)
    class Frozen(Config):
        host: str = "localhost"

    class Child(Frozen):
        pass

    child = Child()
    assert child.host == "localhost"
    with pytest.raises(FrozenInstanceError):
        child.host = "changed"


def test_env_child_of_frozen_parent_is_frozen(monkeypatch):
    @dataclass(frozen=True)
    class Frozen(Config):
        host: str = "localhost"

    class Child(Frozen):
        port: int = env("PLAIN_FROZEN_PORT", 80)

    monkeypatch.setenv("PLAIN_FROZEN_PORT", "8080")
    child = Child()
    assert (child.host, child.port) == ("localhost", 8080)
    with pytest.raises(FrozenInstanceError):
        child.port = 1


def test_undecorated_child_without_env_inherits_resolved_parent(monkeypatch):
    class Parent(Config):
        host: str = env("PLAIN_INHERIT_HOST", "localhost")

    class Child(Parent):
        timeout: int = 5

    monkeypatch.setenv("PLAIN_INHERIT_HOST", "example.test")
    assert (Child().host, Child().timeout) == ("example.test", 5)


class MemoryDriver:
    def __init__(self) -> None:
        self.options: dict[str, object] = {}

    def set_options(self, options: dict[str, object]) -> "MemoryDriver":
        self.options = options
        return self


class MemoryDiskConfig(Config):
    driver: str = "memory"
    prefix: str = env("MEMORY_DISK_PREFIX", "")


class CustomStorageConfig(Config):
    default: str = env("FILESYSTEM_DISK", "memory")
    disks: dict[str, Config] = field(default_factory=lambda: {"memory": MemoryDiskConfig(prefix="app/")})


def test_storage_custom_disk_config_without_dataclass(monkeypatch):
    monkeypatch.delenv("FILESYSTEM_DISK", raising=False)
    manager = StorageManager(None, Dataclass.to_dict(CustomStorageConfig()))
    manager.add_driver("memory", MemoryDriver())

    assert manager.disk("memory").options == {"driver": "memory", "prefix": "app/"}
    assert manager.disk().options == {"driver": "memory", "prefix": "app/"}


def test_storage_custom_disk_reads_environment(monkeypatch):
    monkeypatch.setenv("MEMORY_DISK_PREFIX", "env/")
    assert Dataclass.to_dict(MemoryDiskConfig()) == {"driver": "memory", "prefix": "env/"}
