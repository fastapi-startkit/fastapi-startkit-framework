from typing import Any

from .store import MISSING, expired, expires_at


class ArrayStore:
    def __init__(self) -> None:
        self.storage: dict[str, tuple[float | None, Any]] = {}

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
