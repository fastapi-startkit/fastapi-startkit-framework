from dataclasses import field
from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig(Config):
    title: str = env("APP_NAME", "FastAPI Startkit")
    app_url: str = env("APP_URL", "http://127.0.0.1:8000")
    app: str = "bootstrap.application:app"
    reload: bool = env("APP_RELOAD", True)
    # 'auto' keeps the optional `websockets` package from being required at startup.
    ws: str = env("APP_WS", "auto")
    reload_dirs: list | None = None
    reload_excludes: list = field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
