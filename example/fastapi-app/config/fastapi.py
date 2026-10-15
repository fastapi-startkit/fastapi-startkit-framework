from dataclasses import field
from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig(Config):
    app_url: str = env("APP_URL", "http://127.0.0.1:8000")
    app: str = "bootstrap.application:app"
    reload: bool = env("APP_RELOAD", True)
    reload_dirs: list | None = None
    reload_excludes: list = field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
