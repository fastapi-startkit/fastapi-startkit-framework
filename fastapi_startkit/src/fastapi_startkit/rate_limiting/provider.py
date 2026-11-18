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
        if not self.app.has("cache"):
            return Repository(ArrayStore())
        return self.app.make("cache").store(self.app.make("config").get(f"{self.provider_key}.store"))
