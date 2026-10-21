from pathlib import Path
from typing import Any

from fastapi_startkit.support import Provider

from .config import CacheConfig
from .file_store import FileStore
from .manager import CacheManager
from .store import Store

MIGRATION = "2026_10_21_000000_create_caches_table.py"


class CacheProvider(Provider):
    provider_key = "cache"

    def register(self) -> None:
        config = self.resolve_config(CacheConfig)
        self.merge_config_from(config, self.provider_key)
        manager = CacheManager(config)
        manager.extend("file", lambda store: FileStore(Path(self.app.base_path) / store["path"]))
        manager.extend("database", self.database_store)
        manager.extend("redis", lambda store: self.redis_store(store, config.get("prefix") or ""))
        self.app.bind("cache", manager)

    def database_store(self, store: dict[str, Any]) -> Store:
        from .database_store import DatabaseStore

        return DatabaseStore(lambda: self.app.make("db").connection(store.get("connection")), store["table"])

    def redis_store(self, store: dict[str, Any], prefix: str) -> Store:
        from .redis_store import RedisStore

        return RedisStore(lambda: self.redis().connection(store.get("connection")), prefix)

    def redis(self) -> Any:
        if not self.app.has("redis"):
            raise RuntimeError("The redis cache store requires RedisProvider to be registered.")
        return self.app.make("redis")

    def boot(self) -> None:
        directory = Path(__file__).resolve().parent
        self.publishes(
            {
                directory / "config" / "__init__.py": "config/cache.py",
                directory / "migrations" / MIGRATION: f"databases/migrations/{MIGRATION}",
            }
        )
