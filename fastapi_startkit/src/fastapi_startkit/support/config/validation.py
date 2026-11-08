from collections.abc import Callable, Mapping

from fastapi_startkit.exceptions.exceptions import InvalidConfigurationSetup


class ConfigurationError(InvalidConfigurationSetup):
    def __init__(self, key: str, problem: str):
        self.key = key
        super().__init__(f"Invalid configuration {key!r}: {problem}")


def ensure_config(settings: object, namespace: str) -> None:
    validator = VALIDATORS.get(namespace)
    if validator is None:
        raise ValueError(f"No configuration validator for {namespace!r}")
    validator(settings)


def validate_app_settings(settings: object) -> None:
    for name in ("name", "env", "timezone"):
        require_text(settings, "app", name)
    if not isinstance(require(settings, "app", "debug"), bool):
        raise ConfigurationError("app.debug", "must be a bool")


def validate_database_settings(settings: object) -> None:
    from fastapi_startkit.masoniteorm.config.config import DBConfig

    default = require_text(settings, "database", "default")

    connections = require(settings, "database", "connections")
    if not isinstance(connections, Mapping):
        raise ConfigurationError("database.connections", "must be a mapping of connection names to DBConfig")
    for name, connection in connections.items():
        if not isinstance(connection, DBConfig):
            raise ConfigurationError(f"database.connections.{name}", "must be a DBConfig instance")
    if default not in connections:
        raise ConfigurationError("database.default", f"{default!r} is not one of the configured connections")

    migrations = require(settings, "database", "migrations")
    if not isinstance(migrations, Mapping):
        raise ConfigurationError("database.migrations", "must be a mapping with 'table' and 'directory'")
    for name in ("table", "directory"):
        require_text(migrations, "database.migrations", name)


def require(settings: object, prefix: str, name: str) -> object:
    missing = object()
    found = settings.get(name, missing) if isinstance(settings, Mapping) else getattr(settings, name, missing)
    if found is missing:
        raise ConfigurationError(f"{prefix}.{name}", "is missing")
    return found


def require_text(settings: object, prefix: str, name: str) -> str:
    found = require(settings, prefix, name)
    if not isinstance(found, str) or not found:
        raise ConfigurationError(f"{prefix}.{name}", "must be a non-empty string")
    return found


VALIDATORS: dict[str, Callable[[object], None]] = {
    "app": validate_app_settings,
    "database": validate_database_settings,
}
