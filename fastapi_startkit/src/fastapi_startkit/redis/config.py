import re
from dataclasses import dataclass, field
from typing import Any

from fastapi_startkit.environment import env


def default_prefix() -> str:
    app_name = str(env("APP_NAME", "fastapi", cast=False))
    return re.sub(r"[^a-z0-9]+", "_", app_name.lower()).strip("_") + "_database_"


@dataclass
class RedisConfig:
    client: str = field(default_factory=lambda: env("REDIS_CLIENT", "redis"))

    options: dict[str, Any] = field(
        default_factory=lambda: {
            "prefix": env("REDIS_PREFIX", default_prefix(), cast=False),
        }
    )

    connections: dict[str, dict[str, Any]] = field(
        default_factory=lambda: {
            "default": {
                "url": env("REDIS_URL", None, cast=False),
                "host": env("REDIS_HOST", "127.0.0.1"),
                "username": env("REDIS_USERNAME", None, cast=False),
                "password": env("REDIS_PASSWORD", None, cast=False),
                "port": env("REDIS_PORT", 6379),
                "database": env("REDIS_DB", 0),
            },
            "cache": {
                "url": env("REDIS_URL", None, cast=False),
                "host": env("REDIS_HOST", "127.0.0.1"),
                "username": env("REDIS_USERNAME", None, cast=False),
                "password": env("REDIS_PASSWORD", None, cast=False),
                "port": env("REDIS_PORT", 6379),
                "database": env("REDIS_CACHE_DB", 1),
            },
        }
    )
