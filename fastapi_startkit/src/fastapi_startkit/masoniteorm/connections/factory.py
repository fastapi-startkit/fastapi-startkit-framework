from typing import Any

from sqlalchemy import StaticPool
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

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

    @classmethod
    def build_url(cls, config: dict) -> str:
        if url := config.get("url"):
            return str(url)

        driver = config["driver"]
        scheme = cls.DRIVER_URLS[driver]
        user = config.get("username", "")
        pwd = config.get("password", "")
        host = config.get("host", "localhost")
        port = config.get("port", "")
        db = config.get("database", "")
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

    def make(self, config: dict, name: str) -> type[Connection]:
        engine = self.create_engine(config)
        driver = config["driver"]
        match driver:
            case "sqlite":
                return SQliteConnection(engine, config)
            case "postgres":
                return PostgresConnection(engine, config)
            case "mysql":
                return MySQLConnection(engine, config)

        raise ValueError(f"Unsupported driver: {driver}")
