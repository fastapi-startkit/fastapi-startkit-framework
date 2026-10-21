from pathlib import Path

from fastapi_startkit.support import Provider

from .config import CacheConfig
from .manager import CacheManager


class CacheProvider(Provider):
    provider_key = "cache"

    def register(self) -> None:
        config = self.resolve_config(CacheConfig)
        self.merge_config_from(config, self.provider_key)
        self.app.bind("cache", CacheManager(config))

    def boot(self) -> None:
        self.publishes({Path(__file__).resolve().parent / "config" / "__init__.py": "config/cache.py"})
