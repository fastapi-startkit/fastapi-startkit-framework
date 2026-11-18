from dataclasses import dataclass

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class RateLimiterConfig(Config):
    store: str | None = env("RATE_LIMITER_STORE", None, cast=False)
