from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: env("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: env("REDIS_PORT", 6379))
    db: int = field(default_factory=lambda: env("REDIS_DB", 0))

    options: dict = field(default_factory=lambda: {"decode_responses": True})
