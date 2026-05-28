from dataclasses import dataclass, field
from typing import Dict, Any

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import SQLiteConfig, PostgresConfig


@dataclass
class DatabaseConfig:
    default: str = field(default_factory=lambda: env("DB_CONNECTION", "postgres"))

    connections: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "sqlite": SQLiteConfig(
                driver="sqlite",
                database=env("DB_DATABASE", "database.sqlite"),
                options=None,
            ),
            "postgres": PostgresConfig(
                driver="postgres",
                host=env("DB_HOST", "127.0.0.1"),
                database=env("DB_DATABASE", "forge"),
                username=env("DB_USERNAME", "forge"),
                password=env("DB_PASSWORD", ""),
                port=int(env("DB_PORT", "5432")),
                options=None,
            ),
        }
    )

    migrations: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {"table": "migrations", "path": "databases/migrations"}
    )
