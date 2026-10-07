from pathlib import Path

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
            self.app.add_event_handler("shutdown", self.app.make("redis").disconnect)
        except RuntimeError:
            return
