import functools
import hashlib
import inspect
import pickle
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, overload

from .store import MISSING, Store

if TYPE_CHECKING:
    from .lock import Lock

P = ParamSpec("P")
Ttl = float | timedelta | None


class Decorator(Protocol):
    def __call__(self, function: Callable[P, Any], /) -> Callable[P, Awaitable[Any]]: ...


def call_key(base: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    if not args and not kwargs:
        return base

    arguments = (args, sorted(kwargs.items()))
    try:
        payload = pickle.dumps(arguments)
    except (pickle.PicklingError, TypeError, AttributeError):
        payload = repr(arguments).encode()
    return f"{base}:{hashlib.sha256(payload).hexdigest()[:16]}"


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

    @overload
    def remember(self, key: str, ttl: Ttl, factory: Callable[[], Any]) -> Awaitable[Any]: ...

    @overload
    def remember(self, key: str | None, ttl: Ttl, factory: None = None) -> Decorator: ...

    def remember(
        self, key: str | None, ttl: Ttl, factory: Callable[[], Any] | None = None
    ) -> Awaitable[Any] | Decorator:
        if factory is None:
            return self.decorator(key, ttl)
        if key is None:
            raise ValueError("Cache.remember requires a key when a factory is given.")
        return self.fetch(key, ttl, factory)

    def decorator(self, key: str | None, ttl: Ttl) -> Decorator:
        def decorate(function: Callable[P, Any]) -> Callable[P, Awaitable[Any]]:
            base = key or f"{function.__module__}.{function.__qualname__}"

            @functools.wraps(function)
            async def cached(*args: P.args, **kwargs: P.kwargs) -> Any:
                return await self.fetch(call_key(base, args, kwargs), ttl, lambda: function(*args, **kwargs))

            return cached

        return decorate

    async def fetch(self, key: str, ttl: Ttl, factory: Callable[[], Any]) -> Any:
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

    def lock(self, name: str, seconds: float = 0, owner: str | None = None) -> "Lock":
        factory = getattr(self.store, "lock", None)
        if factory is None:
            raise TypeError(f"Cache store [{type(self.store).__name__}] does not support locks.")
        return factory(self.key(name), seconds, owner)
