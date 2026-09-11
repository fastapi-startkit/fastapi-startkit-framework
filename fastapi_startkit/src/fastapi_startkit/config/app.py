import os
from dataclasses import field, dataclass
from fastapi_startkit.environment.environment import env


@dataclass
class AppConfig:
    name: str = field(default_factory=lambda: os.getenv("APP_NAME", "FastAPI starter kit"))
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    debug: bool = field(default_factory=lambda: env("APP_DEBUG", "true"))
    timezone: str = field(default_factory=lambda: os.getenv("APP_TIMEZONE", "UTC"))
