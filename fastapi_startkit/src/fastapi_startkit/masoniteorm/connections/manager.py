from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.config.database import DatabaseConfig
from fastapi_startkit.masoniteorm.connections.connection import Connection

if TYPE_CHECKING:
    from fastapi_startkit.masoniteorm.connections.factory import ConnectionFactory


class DatabaseManager:
    def __init__(self, factory: "ConnectionFactory", config: DatabaseConfig):
        self.factory = factory
        if not isinstance(config, DatabaseConfig):
            raise TypeError("DatabaseManager requires DatabaseConfig")
        self.config: DatabaseConfig = config
        self.connections: dict[str, Connection] = {}

    def connection(self, name: str | None = None):
        name = self.get_default_connection_name(name)
        assert name is not None
        config = self.config.connections.get(name)

        if config is None:
            raise ValueError(f"Connection '{name}' not found in configuration")

        if name not in self.connections:
            self.connections[name] = self.factory.make(config, name)

        return self.connections[name]

    def disconnect(self):
        pass

    def reconnect(self):
        pass

    def get_default_connection_name(self, name: str | None) -> str:
        if name is None or name == "default":
            return self.config.default
        return name

    def get_schema_builder(self):
        from fastapi_startkit.masoniteorm.schema import Schema

        return Schema(self)

    async def clear(self):
        for conn in self.connections.values():
            await conn.close()
            await conn.engine.dispose()
        self.connections.clear()
