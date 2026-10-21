from collections.abc import Callable
from typing import Any, Self

from .array_store import ArrayStore
from .repository import Repository
from .store import Store

StoreFactory = Callable[[dict[str, Any]], Store]


class CacheManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._stores: dict[str, Repository] = {}
        self._creators: dict[str, StoreFactory] = {"array": lambda config: ArrayStore()}

    def __getattr__(self, method: str) -> Any:
        if method.startswith("_"):
            raise AttributeError(method)
        return getattr(self.store(), method)

    def store(self, name: str | None = None) -> Repository:
        resolved: str = name or self.config.get("default") or "array"
        if resolved not in self._stores:
            self._stores[resolved] = self.resolve(resolved)
        return self._stores[resolved]

    def resolve(self, name: str) -> Repository:
        config = self.config.get("stores", {}).get(name)
        if config is None:
            raise ValueError(f"Cache store [{name}] is not defined.")

        driver = config.get("driver")
        if driver not in self._creators:
            raise ValueError(f"Cache driver [{driver}] is not supported.")
        return Repository(self._creators[driver](config), self.config.get("prefix") or "")

    def extend(self, driver: str, factory: StoreFactory) -> Self:
        self._creators[driver] = factory
        return self
