from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DatabaseConfig as BaseDatabaseConfig
from fastapi_startkit.masoniteorm import DBConfig, SQLiteConfig, PostgresConfig


@dataclass
class DatabaseConfig(BaseDatabaseConfig):
    default: str = env("DB_CONNECTION", "postgres")

    connections: dict[str, DBConfig] = field(
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
                port=env("DB_PORT", 5432),
                options=None,
            ),
        }
    )

    migrations: dict[str, str] = field(default_factory=lambda: {"table": "migrations", "path": "databases/migrations"})
