from typing import TYPE_CHECKING, cast

from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from fastapi_startkit.exceptions.exceptions import DriverNotFound
from fastapi_startkit.masoniteorm.config.config import DBConfig
from fastapi_startkit.masoniteorm.connections.connection import Connection
from fastapi_startkit.masoniteorm.connections.sqlite_connection import SQliteConnection
from fastapi_startkit.masoniteorm.connections.postgres_connection import (
    PostgresConnection,
)
from fastapi_startkit.masoniteorm.connections.mysql_connection import MySQLConnection

if TYPE_CHECKING:
    from fastapi_startkit.application import Application
    from fastapi_startkit.config import AppConfig


class ConnectionFactory:
    CONNECTIONS: dict[str, type[Connection]] = {
        "sqlite": SQliteConnection,
        "mysql": MySQLConnection,
        "postgres": PostgresConnection,
    }

    @classmethod
    def _ensure_supported(cls, driver: str) -> None:
        if driver not in cls.CONNECTIONS:
            supported = ", ".join(sorted(cls.CONNECTIONS))
            raise DriverNotFound(f"Unsupported database driver {driver!r}. Supported drivers are: {supported}.")

    @classmethod
    def build_url(cls, config: DBConfig) -> str:
        if not config.url:
            cls._ensure_supported(config.driver)
        return config.build_url()

    @classmethod
    def create_engine(cls, config: DBConfig) -> AsyncEngine:
        from fastapi_startkit.application import app

        cls._ensure_supported(config.driver)
        application = cast("Application[AppConfig]", app())
        url = cls.CONNECTIONS[config.driver].resolve_url(make_url(config.build_url()), application.base_path)
        options: dict[str, object] = {"echo": config.echo}
        if application.is_testing():
            options["poolclass"] = NullPool
        else:
            options.update(config.engine_options())
        return create_async_engine(url, **options)

    @classmethod
    def create_connection(cls, driver: str, config: DBConfig) -> Connection:
        cls._ensure_supported(driver)
        if driver != config.driver:
            raise ValueError(f"Connection driver {driver!r} does not match configuration driver {config.driver!r}")
        return cls.CONNECTIONS[driver](cls.create_engine(config), config)

    def make(self, config: DBConfig, name: str) -> Connection:
        return self.create_connection(config.driver, config)
