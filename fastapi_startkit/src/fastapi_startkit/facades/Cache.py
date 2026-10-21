import functools
from collections.abc import Callable
from typing import Any

from .Facade import Facade


def manager() -> Any:
    from ..application import app

    return app().make("cache")


class Cache(metaclass=Facade):
    key = "cache"

    @staticmethod
    def remember(key: str | None, ttl: Any, factory: Callable[[], Any] | None = None) -> Any:
        if factory is not None:
            return manager().remember(key, ttl, factory)

        def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(function)
            async def cached(*args: Any, **kwargs: Any) -> Any:
                return await manager().remember(key, ttl)(function)(*args, **kwargs)

            return cached

        return decorate
