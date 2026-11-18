import inspect
import time
from collections.abc import Callable
from typing import Any, Self

from fastapi_startkit.cache import Repository

from .exceptions import LimiterNotDefinedException

LimiterCallback = Callable[[Any], Any]


class RateLimiter:
    def __init__(self, cache: Callable[[], Repository]):
        self.resolve_cache = cache
        self.repository: Repository | None = None
        self.limiters: dict[str, LimiterCallback] = {}

    @property
    def cache(self) -> Repository:
        if self.repository is None:
            self.repository = self.resolve_cache()
        return self.repository

    def for_(self, name: str, callback: LimiterCallback) -> Self:
        self.limiters[name] = callback
        return self

    def limiter(self, name: str) -> LimiterCallback:
        if name not in self.limiters:
            raise LimiterNotDefinedException(f"Rate limiter [{name}] is not defined.")
        return self.limiters[name]

    async def attempt(self, key: str, max_attempts: int, callback: Callable[[], Any], decay_seconds: int = 60) -> Any:
        if await self.too_many_attempts(key, max_attempts):
            return False

        result = callback()
        if inspect.isawaitable(result):
            result = await result
        await self.hit(key, decay_seconds)
        return True if result is None else result

    async def too_many_attempts(self, key: str, max_attempts: int) -> bool:
        return await self.attempts(key) >= max_attempts

    async def hit(self, key: str, decay_seconds: int = 60) -> int:
        return await self.increment(key, decay_seconds)

    async def increment(self, key: str, decay_seconds: int = 60, amount: int = 1) -> int:
        now = self.now()
        available_at = await self.available_at(key)
        if available_at is None:
            available_at = now + decay_seconds
            await self.cache.put(self.timer_key(key), available_at, decay_seconds)
            hits = amount
        else:
            hits = await self.cache.get(key, 0) + amount

        await self.cache.put(key, hits, available_at - now)
        return hits

    async def decrement(self, key: str, decay_seconds: int = 60, amount: int = 1) -> int:
        return await self.increment(key, decay_seconds, -amount)

    async def attempts(self, key: str) -> int:
        if await self.available_at(key) is None:
            return 0
        return await self.cache.get(key, 0)

    async def reset_attempts(self, key: str) -> bool:
        return await self.cache.forget(key)

    async def remaining(self, key: str, max_attempts: int) -> int:
        return max(0, max_attempts - await self.attempts(key))

    async def retries_left(self, key: str, max_attempts: int) -> int:
        return await self.remaining(key, max_attempts)

    async def clear(self, key: str) -> None:
        await self.reset_attempts(key)
        await self.cache.forget(self.timer_key(key))

    async def available_in(self, key: str) -> int:
        available_at = await self.available_at(key)
        return 0 if available_at is None else available_at - self.now()

    async def available_at(self, key: str) -> int | None:
        available_at = await self.cache.get(self.timer_key(key))
        if available_at is None or available_at <= self.now():
            return None
        return available_at

    @staticmethod
    def timer_key(key: str) -> str:
        return f"{key}:timer"

    @staticmethod
    def now() -> int:
        return int(time.time())
