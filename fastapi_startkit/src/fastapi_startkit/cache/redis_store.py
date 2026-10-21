import base64
import math
import pickle
import re
from collections.abc import Callable
from typing import Any

from fastapi_startkit.redis import Connection

from .lock import Lock
from .store import MISSING

GLOB = re.compile(r"([*?\[\]\\])")
RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class RedisStore:
    def __init__(self, connection: Callable[[], Connection], prefix: str, batch: int = 500):
        if not prefix:
            raise ValueError("Redis cache store requires a non-empty prefix.")
        self.connection = connection
        self.prefix = prefix
        self.batch = batch

    async def get(self, key: str) -> Any:
        payload = await self.connection().get(key)
        if payload is None:
            return MISSING
        try:
            return pickle.loads(base64.b64decode(payload))
        except Exception:
            await self.forget(key)
            return MISSING

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        payload = base64.b64encode(pickle.dumps(value)).decode()
        milliseconds = None if seconds is None else max(1, math.ceil(seconds * 1000))
        return bool(await self.connection().set(key, payload, px=milliseconds))

    async def forget(self, key: str) -> bool:
        return bool(await self.connection().delete(key))

    async def flush(self) -> bool:
        connection = self.connection()
        namespace = f"{connection.prefix}{self.prefix}:"
        pattern = GLOB.sub(r"\\\1", namespace) + "*"
        keys: list[Any] = []
        async for key in connection.scan_iter(match=pattern, count=self.batch):
            keys.append(strip(key, connection.prefix))
            if len(keys) >= self.batch:
                await connection.unlink(*keys)
                keys.clear()
        if keys:
            await connection.unlink(*keys)
        return True

    def lock(self, name: str, seconds: float = 0, owner: str | None = None) -> "RedisLock":
        return RedisLock(self, name, seconds, owner)


class RedisLock(Lock):
    def __init__(self, store: RedisStore, name: str, seconds: float = 0, owner: str | None = None):
        super().__init__(name, seconds, owner)
        self.store = store
        self.key = f"lock:{name}"

    async def acquire(self) -> bool:
        milliseconds = None if self.ttl is None else max(1, math.ceil(self.ttl * 1000))
        return bool(await self.store.connection().set(self.key, self.owner, nx=True, px=milliseconds))

    async def release(self) -> bool:
        return bool(await self.store.connection().eval(RELEASE, 1, self.key, self.owner))

    async def force_release(self) -> None:
        await self.store.connection().delete(self.key)


def strip(key: Any, prefix: str) -> Any:
    marker = prefix.encode() if isinstance(key, bytes) else prefix
    return key[len(marker) :]
