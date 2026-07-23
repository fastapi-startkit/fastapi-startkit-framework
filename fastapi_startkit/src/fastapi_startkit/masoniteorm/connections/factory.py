from typing import Any

from sqlalchemy import StaticPool
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from fastapi_startkit.exceptions.exceptions import DriverNotFound
from fastapi_startkit.masoniteorm.connections.connection import Connection
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.connections.postgres_connection import (
    PostgresConnection,
)
from fastapi_startkit.masoniteorm.connections.mysql_connection import MySQLConnection


class ConnectionFactory:
    DRIVER_URLS = {
        "sqlite": "sqlite+aiosqlite",
        "mysql": "mysql+aiomysql",
        "postgres": "postgresql+asyncpg",
    }

    # Sensible per-driver defaults so a missing/empty "port" no longer surfaces as a
    # raw SQLAlchemy `ValueError: invalid literal for int()` at engine-creation time.
    DEFAULT_PORTS = {
        "mysql": 3306,
        "postgres": 5432,
    }

    CONNECTIONS = {
        "sqlite": SQliteConnection,
        "mysql": MySQLConnection,
        "postgres": PostgresConnection,
    }

    @classmethod
    def _unsupported_driver_error(cls, driver: Any) -> DriverNotFound:
        supported = ", ".join(sorted(cls.DRIVER_URLS))
        return DriverNotFound(f"Unsupported database driver {driver!r}. Supported drivers are: {supported}.")

    @classmethod
    def build_url(cls, config: dict) -> str:
        if url := config.get("url"):
            return str(url)

        driver = config["driver"]
        scheme = cls.DRIVER_URLS.get(driver)
        if scheme is None:
            raise cls._unsupported_driver_error(driver)
        db = config.get("database", "")

        if driver == "sqlite":
            return f"{scheme}:///{db}"

        user = config.get("username", "")
        pwd = config.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port") or cls.DEFAULT_PORTS[driver]
        return f"{scheme}://{user}:{pwd}@{host}:{port}/{db}"

    @classmethod
    def create_engine(cls, cfg: dict) -> AsyncEngine:
        url = cls.build_url(cfg)
        kwargs: dict[str, Any] = {"echo": True}
        from fastapi_startkit.application import app

        if app().is_testing():
            kwargs["poolclass"] = NullPool
        elif cfg["driver"] == "sqlite":
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = StaticPool
        return create_async_engine(url, **kwargs)

    def make(self, config: dict, name: str) -> Connection:
        driver = config["driver"]
        connection_class = type(self).CONNECTIONS.get(driver)
        if connection_class is None:
            raise type(self)._unsupported_driver_error(driver)

        engine = self.create_engine(config)
        return connection_class(engine, config)
