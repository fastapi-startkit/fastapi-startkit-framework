import asyncio
import weakref
from contextvars import ContextVar
from typing import Any

from .store import Store

Memo = dict["MemoStore", dict[str, Any]]

_scope: ContextVar[tuple[weakref.ref[asyncio.Task[Any]], Memo] | None] = ContextVar("cache_memo", default=None)


def memo() -> Memo:
    task = asyncio.current_task()
    state = _scope.get()
    if state is not None and task is not None and state[0]() is task:
        return state[1]

    fresh: Memo = {}
    if task is not None:
        _scope.set((weakref.ref(task), fresh))
    return fresh


class MemoStore:
    def __init__(self, store: Store):
        self.store = store

    def values(self) -> dict[str, Any]:
        return memo().setdefault(self, {})

    async def get(self, key: str) -> Any:
        values = self.values()
        if key not in values:
            values[key] = await self.store.get(key)
        return values[key]

    async def put(self, key: str, value: Any, seconds: float | None) -> bool:
        self.values().pop(key, None)
        return await self.store.put(key, value, seconds)

    async def forget(self, key: str) -> bool:
        self.values().pop(key, None)
        return await self.store.forget(key)

    async def flush(self) -> bool:
        self.values().clear()
        return await self.store.flush()
