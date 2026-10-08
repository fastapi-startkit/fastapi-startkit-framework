from collections.abc import Awaitable, Callable, Iterable
from typing import Any, overload

from redis.asyncio.client import Pipeline
from redis.asyncio.client import Redis as AsyncRedis

from fastapi_startkit.redis import Connection, RedisManager

class RedisFacade(AsyncRedis):
    def connection(self, name: str | None = None) -> Connection: ...  # pyright: ignore[reportIncompatibleVariableOverride]
    def connections(self) -> dict[str, Connection]: ...
    def extend(self, client: str, factory: Callable[[dict[str, Any]], Any]) -> RedisManager: ...
    async def purge(self, name: str | None = None) -> None: ...
    async def disconnect(self) -> None: ...
    async def command(self, method: str, parameters: Iterable[Any] | None = None) -> Any: ...  # pyright: ignore[reportIncompatibleMethodOverride]
    @overload
    def pipeline(self, callback: None = None) -> Pipeline: ...
    @overload
    def pipeline(self, callback: Callable[[Pipeline], Any]) -> Awaitable[list[Any]]: ...  # pyright: ignore[reportIncompatibleMethodOverride]
    @overload
    def transaction(self, callback: None = None) -> Pipeline: ...
    @overload
    def transaction(self, callback: Callable[[Pipeline], Any]) -> Awaitable[list[Any]]: ...  # pyright: ignore[reportIncompatibleMethodOverride]
    async def subscribe(self, channels: str | Iterable[str], callback: Callable[[Any, Any], Any]) -> None: ...
    async def psubscribe(self, patterns: str | Iterable[str], callback: Callable[[Any, Any], Any]) -> None: ...

Redis: RedisFacade
