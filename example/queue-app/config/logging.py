from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class LoggingConfig(Config):
    level: str = env("LOG_LEVEL", "debug")
    channel: str = env("LOG_CHANNEL", "daily")
