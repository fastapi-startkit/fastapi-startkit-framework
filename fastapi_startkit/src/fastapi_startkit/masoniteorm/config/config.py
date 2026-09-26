from typing import Optional, Dict, Any
from pydantic.dataclasses import dataclass
from fastapi_startkit.environment.environment import env


@dataclass
class SQLiteConfig:
    driver: str = "sqlite"
    url: Optional[str] = env("DB_URL", None, cast=False)
    database: str = env("DB_DATABASE", "database.sqlite")
    options: Optional[Dict[str, Any]] = None


@dataclass
class MySQLConfig:
    driver: str = "mysql"
    url: Optional[str] = env("DB_URL", None, cast=False)
    host: str = env("DB_HOST", "127.0.0.1")
    port: int = env("DB_PORT", 3306)
    database: str = env("DB_DATABASE", "inertia")
    username: str = env("DB_USERNAME", "root")
    password: str = env("DB_PASSWORD", "", cast=False)
    unix_socket: str = env("DB_SOCKET", "", cast=False)
    charset: str = env("DB_CHARSET", "utf8mb4")
    collation: str = env("DB_COLLATION", "utf8mb4_unicode_ci")
    options: Optional[Dict[str, Any]] = None


@dataclass
class PostgresConfig:
    driver: str = "postgres"
    url: Optional[str] = env("DB_URL", None, cast=False)
    host: str = env("DB_HOST", "127.0.0.1")
    port: int = env("DB_PORT", 5432)
    database: str = env("DB_DATABASE", "inertia")
    username: str = env("DB_USERNAME", "postgres")
    password: str = env("DB_PASSWORD", "", cast=False)
    charset: str = env("DB_CHARSET", "utf8")
    sslmode: str = env("DB_SSLMODE", "prefer")
    options: Optional[Dict[str, Any]] = None
