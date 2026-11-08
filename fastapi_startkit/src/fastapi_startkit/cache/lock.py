import asyncio
import secrets
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .repository import evaluate


class LockTimeoutError(Exception):
    pass


class Lock(ABC):
    sleep: float = 0.25

    def __init__(self, name: str, seconds: float = 0, owner: str | None = None):
        self.name = name
        self.seconds = seconds
        self.owner = owner or secrets.token_hex(16)

    @property
    def ttl(self) -> float | None:
        return self.seconds if self.seconds > 0 else None

    @abstractmethod
    async def acquire(self) -> bool: ...

    @abstractmethod
    async def release(self) -> bool: ...

    @abstractmethod
    async def force_release(self) -> None: ...

    async def get(self, callback: Callable[[], Any] | None = None) -> Any:
        if not await self.acquire():
            return False
        if callback is None:
            return True
        return await self.run(callback)

    async def block(self, seconds: float, callback: Callable[[], Any] | None = None) -> Any:
        deadline = time.monotonic() + seconds
        while not await self.acquire():
            if time.monotonic() >= deadline:
                raise LockTimeoutError(f"Could not acquire lock [{self.name}] within {seconds} seconds.")
            await asyncio.sleep(self.sleep)
        if callback is None:
            return True
        return await self.run(callback)

    async def run(self, callback: Callable[[], Any]) -> Any:
        try:
            return await evaluate(callback)
        finally:
            await self.release()

    async def __aenter__(self) -> "Lock":
        if not await self.acquire():
            raise LockTimeoutError(f"Lock [{self.name}] is held by another owner.")
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.release()
