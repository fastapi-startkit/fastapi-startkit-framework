from dataclasses import dataclass, field
from typing import Any

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm.config.config import MySQLConfig, PostgresConfig, SQLiteConfig


@dataclass
class DatabaseConfig:
    default: str = field(default_factory=lambda: env("DB_CONNECTION", "pgsql"))

    connections: dict[str, SQLiteConfig | MySQLConfig | PostgresConfig | dict[str, Any]] = field(
        default_factory=lambda: {
            "sqlite": SQLiteConfig(
                driver="sqlite",
                database=env("DB_DATABASE", "database.sqlite"),
                options=None,
            ),
        }
    )

    migrations: dict[str, str] = field(
        default_factory=lambda: {"table": "migrations", "directory": "databases/migrations"}
    )
