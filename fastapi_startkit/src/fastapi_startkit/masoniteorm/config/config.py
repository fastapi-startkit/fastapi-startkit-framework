from fastapi_startkit.configuration import Config
from typing import Any, Protocol, runtime_checkable
from dataclasses import dataclass

from sqlalchemy import StaticPool

from fastapi_startkit.environment import env


@runtime_checkable
class DBConfig(Protocol):
    driver: str
    url: str | None
    database: str
    echo: bool
    options: dict[str, Any] | None
    schema: str | None

    def build_url(self) -> str: ...

    def engine_options(self) -> dict[str, object]: ...


@dataclass
class SQLiteConfig(Config):
    driver: str = "sqlite"
    url: str | None = env("DB_URL", "")
    database: str = env("DB_DATABASE", "database.sqlite")
    echo: bool = env("DB_ECHO", False)
    options: dict[str, Any] | None = None
    schema: str | None = None

    def build_url(self) -> str:
        return self.url or f"sqlite+aiosqlite:///{self.database}"

    def engine_options(self) -> dict[str, object]:
        return {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}


@dataclass
class MySQLConfig(Config):
    driver: str = "mysql"
    url: str | None = env("DB_URL", "")
    host: str = env("DB_HOST", "127.0.0.1")
    port: int = env("DB_PORT", 3306)
    database: str = env("DB_DATABASE", "inertia")
    username: str = env("DB_USERNAME", "root")
    password: str = env("DB_PASSWORD", "")
    unix_socket: str = env("DB_SOCKET", "")
    charset: str = env("DB_CHARSET", "utf8mb4")
    collation: str = env("DB_COLLATION", "utf8mb4_unicode_ci")
    echo: bool = env("DB_ECHO", False)
    options: dict[str, Any] | None = None
    schema: str | None = None

    def build_url(self) -> str:
        port = self.port or 3306
        return self.url or f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{port}/{self.database}"

    def engine_options(self) -> dict[str, object]:
        return {}


@dataclass
class PostgresConfig(Config):
    driver: str = "postgres"
    url: str | None = env("DB_URL", "")
    host: str = env("DB_HOST", "127.0.0.1")
    port: int = env("DB_PORT", 5432)
    database: str = env("DB_DATABASE", "inertia")
    username: str = env("DB_USERNAME", "postgres")
    password: str = env("DB_PASSWORD", "")
    charset: str = env("DB_CHARSET", "utf8")
    sslmode: str = env("DB_SSLMODE", "prefer")
    echo: bool = env("DB_ECHO", False)
    options: dict[str, Any] | None = None
    schema: str | None = None

    def build_url(self) -> str:
        port = self.port or 5432
        return self.url or f"postgresql+asyncpg://{self.username}:{self.password}@{self.host}:{port}/{self.database}"

    def engine_options(self) -> dict[str, object]:
        return {}
