import os
import re
from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


def default_prefix() -> str:
    app_name = os.getenv("APP_NAME") or "fastapi"
    return re.sub(r"[^a-z0-9]+", "_", app_name.lower()).strip("_") + "_database_"


@dataclass
class RedisOptions(Config):
    prefix: str = field(default_factory=lambda: os.getenv("REDIS_PREFIX") or default_prefix())


@dataclass
class RedisConnectionConfig(Config):
    url: str | None = env("REDIS_URL", None, cast=False)
    host: str = env("REDIS_HOST", "127.0.0.1")
    username: str | None = env("REDIS_USERNAME", None, cast=False)
    password: str | None = env("REDIS_PASSWORD", None, cast=False)
    port: int = env("REDIS_PORT", 6379)
    database: int = env("REDIS_DB", 0)


@dataclass
class RedisConfig(Config):
    client: str = env("REDIS_CLIENT", "redis")

    options: RedisOptions = field(default_factory=RedisOptions)

    connections: dict[str, RedisConnectionConfig] = field(
        default_factory=lambda: {
            "default": RedisConnectionConfig(),
            "cache": RedisConnectionConfig(database=env("REDIS_CACHE_DB", 1)),
        }
    )
