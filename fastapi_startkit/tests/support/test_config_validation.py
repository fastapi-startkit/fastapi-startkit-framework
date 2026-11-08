from dataclasses import dataclass, field

import pytest

from fastapi_startkit.config import AppConfig
from fastapi_startkit.exceptions import InvalidConfigurationSetup
from fastapi_startkit.masoniteorm import DatabaseConfig, DBConfig, SQLiteConfig
from fastapi_startkit.support.config import ConfigurationError, ensure_config


@dataclass
class DatabaseSettings:
    default: object = "sqlite"
    connections: object = field(default_factory=lambda: {"sqlite": SQLiteConfig()})
    migrations: object = field(default_factory=lambda: {"table": "migrations", "directory": "databases/migrations"})


@dataclass
class WithoutDefault:
    connections: dict[str, DBConfig] = field(default_factory=lambda: {"sqlite": SQLiteConfig()})
    migrations: dict[str, str] = field(
        default_factory=lambda: {"table": "migrations", "directory": "databases/migrations"}
    )


@dataclass
class WithoutMigrations:
    default: str = "sqlite"
    connections: dict[str, DBConfig] = field(default_factory=lambda: {"sqlite": SQLiteConfig()})


@dataclass
class AppSettings:
    name: object = "app"
    env: object = "testing"
    debug: object = False
    timezone: object = "UTC"


def test_valid_database_settings_pass():
    assert ensure_config(DatabaseSettings(), "database") is None
    assert ensure_config(DatabaseConfig(), "database") is None


def test_missing_default_is_reported():
    with pytest.raises(ConfigurationError, match="'database.default': is missing") as error:
        ensure_config(WithoutDefault(), "database")

    assert error.value.key == "database.default"


def test_empty_default_is_reported():
    with pytest.raises(ConfigurationError, match="'database.default': must be a non-empty string"):
        ensure_config(DatabaseSettings(default=""), "database")


def test_default_must_be_a_configured_connection():
    with pytest.raises(
        ConfigurationError, match="'database.default': 'mysql' is not one of the configured connections"
    ):
        ensure_config(DatabaseSettings(default="mysql"), "database")


def test_connections_must_be_a_mapping():
    with pytest.raises(ConfigurationError, match="'database.connections': must be a mapping"):
        ensure_config(DatabaseSettings(connections=[SQLiteConfig()]), "database")


def test_each_connection_must_be_a_db_config():
    with pytest.raises(ConfigurationError, match="'database.connections.sqlite': must be a DBConfig instance"):
        ensure_config(DatabaseSettings(connections={"sqlite": {"driver": "sqlite"}}), "database")


def test_missing_migrations_is_reported():
    with pytest.raises(ConfigurationError, match="'database.migrations': is missing"):
        ensure_config(WithoutMigrations(), "database")


def test_migrations_must_be_a_mapping():
    with pytest.raises(ConfigurationError, match="'database.migrations': must be a mapping"):
        ensure_config(DatabaseSettings(migrations="databases/migrations"), "database")


@pytest.mark.parametrize("key", ["table", "directory"])
def test_missing_migrations_key_is_reported(key: str):
    migrations = {"table": "migrations", "directory": "databases/migrations"}
    del migrations[key]

    with pytest.raises(ConfigurationError, match=f"'database.migrations.{key}': is missing"):
        ensure_config(DatabaseSettings(migrations=migrations), "database")


def test_migrations_values_must_be_non_empty_strings():
    with pytest.raises(ConfigurationError, match="'database.migrations.directory': must be a non-empty string"):
        ensure_config(DatabaseSettings(migrations={"table": "migrations", "directory": ""}), "database")


def test_valid_app_settings_pass():
    assert ensure_config(AppSettings(), "app") is None
    assert ensure_config(AppConfig(), "app") is None


def test_app_debug_must_be_a_bool():
    with pytest.raises(ConfigurationError, match="'app.debug': must be a bool"):
        ensure_config(AppSettings(debug="false"), "app")


def test_app_name_must_be_a_non_empty_string():
    with pytest.raises(ConfigurationError, match="'app.name': must be a non-empty string"):
        ensure_config(AppSettings(name=""), "app")


def test_configuration_error_is_an_invalid_configuration_setup():
    assert issubclass(ConfigurationError, InvalidConfigurationSetup)


def test_unknown_namespace_is_rejected():
    with pytest.raises(ValueError, match="No configuration validator for 'redis'"):
        ensure_config(object(), "redis")
