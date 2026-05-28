import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class LoggingConfig:
    level: str = dataclasses.field(default_factory=lambda: env("LOG_LEVEL", "debug"))
    channel: str = dataclasses.field(
        default_factory=lambda: env("LOG_CHANNEL", "daily")
    )
