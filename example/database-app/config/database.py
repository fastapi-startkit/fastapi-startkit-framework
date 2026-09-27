from dataclasses import field
from typing import Dict, Any

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import MySQLConfig, SQLiteConfig
from pydantic.dataclasses import dataclass


@dataclass
class DatabaseConfig:
    default: str = field(default_factory=lambda: env("DB_CONNECTION", "mysql"))

    connections: dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "sqlite": SQLiteConfig(
                driver="sqlite",
                database=env("DB_DATABASE", "database.sqlite"),
            ),
            "mysql": MySQLConfig(
                driver="mysql",
                host=env("DB_HOST", "127.0.0.1"),
                database=env("DB_DATABASE", "laravel"),
                username=env("DB_USERNAME", "root"),
                password=env("DB_PASSWORD", ""),
                port=env("DB_PORT", "3306"),
                options={"charset": "utf8mb4"},
            ),
        }
    )
