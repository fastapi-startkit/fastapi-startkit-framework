from fastapi_startkit.configuration import Config
import os
from dataclasses import dataclass, field
from fastapi_startkit.environment import env as environment_value


@dataclass
class AppConfig(Config):
    name: str = field(default_factory=lambda: os.getenv("APP_NAME", "FastAPI starter kit"))
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    debug: bool = environment_value("APP_DEBUG", True)
    timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "UTC"))
