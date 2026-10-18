from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.masoniteorm import DatabaseConfig as BaseDatabaseConfig
from fastapi_startkit.masoniteorm import DBConfig, MySQLConfig, SQLiteConfig


@dataclass
class DatabaseConfig(BaseDatabaseConfig):
    default: str = env("DB_CONNECTION", "mysql")

    connections: dict[str, DBConfig] = field(
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
                port=env("DB_PORT", 3306),
                options={"charset": "utf8mb4"},
            ),
        }
    )
