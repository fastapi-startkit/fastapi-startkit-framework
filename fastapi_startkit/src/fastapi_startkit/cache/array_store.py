from typing import Any

from .lock import Lock
from .store import MISSING, expired, expires_at


class ArrayStore:
    def __init__(self) -> None:
        self.storage: dict[str, tuple[float | None, Any]] = {}
        self.locks: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> Any:
        entry = self.storage.get(key)
        if entry is None:
            return MISSING

        expiration, value = entry
        if expired(expiration):
            del self.storage[key]
            return MISSING
        return value

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        self.storage[key] = (expires_at(seconds), value)
        return True

    async def forget(self, key: str) -> bool:
        return self.storage.pop(key, MISSING) is not MISSING

    async def flush(self) -> bool:
        self.storage.clear()
        return True

    def lock(self, name: str, seconds: float = 0, owner: str | None = None) -> "ArrayLock":
        return ArrayLock(self, name, seconds, owner)


class ArrayLock(Lock):
    def __init__(self, store: ArrayStore, name: str, seconds: float = 0, owner: str | None = None):
        super().__init__(name, seconds, owner)
        self.store = store

    def holder(self) -> str | None:
        entry = self.store.locks.get(self.name)
        if entry is None or expired(entry[1]):
            return None
        return entry[0]

    async def acquire(self) -> bool:
        if self.holder() is not None:
            return False
        self.store.locks[self.name] = (self.owner, expires_at(self.ttl))
        return True

    async def release(self) -> bool:
        if self.holder() != self.owner:
            return False
        del self.store.locks[self.name]
        return True

    async def force_release(self) -> None:
        self.store.locks.pop(self.name, None)
