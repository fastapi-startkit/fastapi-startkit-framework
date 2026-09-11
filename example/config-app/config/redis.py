from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: env('REDIS_HOST'))
    port: int = field(default_factory=lambda: env('REDIS_PORT'))
    db: int = field(default_factory=lambda: env('REDIS_DB'))

    options: dict = field(default_factory=lambda: {
        'decode_responses': True
    })
