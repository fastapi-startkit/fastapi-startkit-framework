from dataclasses import field
from fastapi_startkit.configuration import Config
import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig(Config):
    host: str = env("APP_HOST", "127.0.0.1")
    port: int = env("APP_PORT", 8000)
    reload: bool = env("APP_RELOAD", True)
    reload_dirs: list[str] | None = None
    reload_excludes: list[str] = field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
