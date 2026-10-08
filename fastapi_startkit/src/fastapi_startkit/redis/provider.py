from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi_startkit.support import Provider

from .config import RedisConfig
from .manager import RedisManager


class RedisProvider(Provider):
    provider_key = "redis"

    def register(self) -> None:
        config = self.resolve_config(RedisConfig)
        self.merge_config_from(config, self.provider_key)
        self.app.bind("redis", RedisManager(config))

    def boot(self) -> None:
        self.publishes({Path(__file__).resolve().parent / "config.py": "config/redis.py"})

        try:
            router = self.app.fastapi.router
        except RuntimeError:
            return

        manager: RedisManager = self.app.make("redis")
        lifespan = router.lifespan_context

        @asynccontextmanager
        async def disconnecting_lifespan(app: Any) -> AsyncIterator[Any]:
            try:
                async with lifespan(app) as state:
                    yield state
            finally:
                await manager.disconnect()

        router.lifespan_context = disconnecting_lifespan
