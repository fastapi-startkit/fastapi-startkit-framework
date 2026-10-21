import time
from typing import Any, Final, Protocol, final


@final
class Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Final = Missing()


class Store(Protocol):
    async def get(self, key: str) -> Any: ...

    async def put(self, key: str, value: Any, seconds: float | None) -> bool: ...

    async def forget(self, key: str) -> bool: ...

    async def flush(self) -> bool: ...


def expires_at(seconds: float | None) -> float | None:
    return None if seconds is None else time.time() + seconds


def expired(expiration: float | None) -> bool:
    return expiration is not None and expiration <= time.time()
