from pathlib import Path
from typing import override

from fastapi_startkit.cache import ArrayStore, Repository
from fastapi_startkit.support import Provider

from .config import RateLimiterConfig
from .limiter import RateLimiter


class RateLimiterProvider(Provider):
    provider_key = "rate_limiter"

    @override
    def register(self) -> None:
        self.merge_config_from(self.resolve_config(RateLimiterConfig), self.provider_key)
        self.app.bind("rate_limiter", RateLimiter(self.cache))

    def cache(self) -> Repository:
        store = self.app.make("config").get(f"{self.provider_key}.store")
        if self.app.has("cache"):
            return self.app.make("cache").store(store)
        if store is not None:
            raise RuntimeError(f"The [{store}] rate limiter store requires CacheProvider to be registered.")
        return Repository(ArrayStore())

    @override
    def boot(self) -> None:
        directory = Path(__file__).resolve().parent
        self.publishes({directory / "config" / "__init__.py": "config/rate_limiter.py"})
