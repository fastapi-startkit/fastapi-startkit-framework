from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm.config.config import DBConfig, MySQLConfig, PostgresConfig, SQLiteConfig


@runtime_checkable
class DatabaseSettings(Protocol):
    @property
    def default(self) -> str: ...

    @property
    def connections(self) -> Mapping[str, DBConfig]: ...

    @property
    def migrations(self) -> Mapping[str, str]: ...


@dataclass
class DatabaseConfig(Config):
    default: str = env("DB_CONNECTION", "sqlite")

    connections: dict[str, DBConfig] = field(
        default_factory=lambda: {
            "sqlite": SQLiteConfig(database=env("DB_DATABASE", "databases/sqlite.db")),
            "mysql": MySQLConfig(),
            "postgres": PostgresConfig(),
        }
    )

    migrations: dict[str, str] = field(
        default_factory=lambda: {
            "table": "migrations",
            "directory": "databases/migrations",
        }
    )
