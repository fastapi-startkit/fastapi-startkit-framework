from collections.abc import Callable
from typing import Any

from .connection import Connection
from .connector import connect

ClientFactory = Callable[[dict[str, Any]], Any]


class RedisManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._connections: dict[str, Connection] = {}
        self._creators: dict[str, ClientFactory] = {"redis": connect}

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)
        return getattr(self.connection(), method)

    def connection(self, name: str | None = None) -> Connection:
        name = name or "default"
        if name not in self._connections:
            self._connections[name] = self.resolve(name)
        return self._connections[name]

    def resolve(self, name: str) -> Connection:
        config = self.config.get("connections", {}).get(name)
        if config is None:
            raise ValueError(f"Redis connection [{name}] not configured.")

        config = dict(config)
        options = {**self.config.get("options", {}), **(config.pop("options", None) or {})}
        client = self._creator()(self._parameters(config))
        return Connection(client, name, options.get("prefix") or "")

    def extend(self, client: str, factory: ClientFactory) -> "RedisManager":
        self._creators[client] = factory
        return self

    def connections(self) -> dict[str, Connection]:
        return dict(self._connections)

    async def purge(self, name: str | None = None) -> None:
        connection = self._connections.pop(name or "default", None)
        if connection is not None:
            await connection.disconnect()

    async def disconnect(self) -> None:
        for name in list(self._connections):
            await self.purge(name)

    def _creator(self) -> ClientFactory:
        client = self.config.get("client") or "redis"
        if client not in self._creators:
            raise ValueError(f"Redis client [{client}] is not supported.")
        return self._creators[client]

    @staticmethod
    def _parameters(config: dict[str, Any]) -> dict[str, Any]:
        if "database" in config:
            config["db"] = config.pop("database")
        if config.get("url"):
            for key in ("host", "port"):
                config.pop(key, None)
        return {"decode_responses": True, **{key: value for key, value in config.items() if value is not None}}
