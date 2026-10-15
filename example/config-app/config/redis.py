from fastapi_startkit.configuration import Config
from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class RedisConfig(Config):
    host: str = env("REDIS_HOST", "localhost")
    port: int = env("REDIS_PORT", 6379)
    db: int = env("REDIS_DB", 0)
    options: dict = field(default_factory=lambda: {"decode_responses": True})
