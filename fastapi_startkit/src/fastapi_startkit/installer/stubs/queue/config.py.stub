from dataclasses import dataclass

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class QueueConfig(Config):
    driver: str = env("QUEUE_DRIVER", "redis")
    url: str = env("QUEUE_URL", "redis://127.0.0.1:6379/0")
