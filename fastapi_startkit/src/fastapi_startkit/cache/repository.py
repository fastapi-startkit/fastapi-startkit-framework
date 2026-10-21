import inspect
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from .store import MISSING, Store

Ttl = float | timedelta | None


async def evaluate(value: Any) -> Any:
    if callable(value):
        value = value()
    if inspect.isawaitable(value):
        value = await value
    return value


def seconds(ttl: Ttl) -> float | None:
    return ttl.total_seconds() if isinstance(ttl, timedelta) else ttl


class Repository:
    def __init__(self, store: Store, prefix: str = ""):
        self.store = store
        self.prefix = prefix

    def key(self, key: str) -> str:
        return f"{self.prefix}:{key}" if self.prefix else key

    async def get(self, key: str, default: Any = None) -> Any:
        value = await self.store.get(self.key(key))
        return await evaluate(default) if value is MISSING else value

    async def has(self, key: str) -> bool:
        return await self.store.get(self.key(key)) is not MISSING

    async def put(self, key: str, value: Any, ttl: Ttl = None) -> bool:
        duration = seconds(ttl)
        if duration is not None and duration <= 0:
            await self.forget(key)
            return False
        return await self.store.put(self.key(key), value, duration)

    async def forever(self, key: str, value: Any) -> bool:
        return await self.put(key, value)

    async def remember(self, key: str, ttl: Ttl, factory: Callable[[], Any]) -> Any:
        value = await self.store.get(self.key(key))
        if value is not MISSING:
            return value

        value = await evaluate(factory)
        await self.put(key, value, ttl)
        return value

    async def forget(self, key: str) -> bool:
        return await self.store.forget(self.key(key))

    async def flush(self) -> bool:
        return await self.store.flush()
