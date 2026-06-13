import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig:
    """Server configuration for the uvicorn/FastAPI serve command.

    All fields can be overridden via environment variables or by publishing a
    ``config/fastapi.py`` file in the application root.

    Resolution order for host/port (highest priority wins):
      CLI --host / --port  >  APP_HOST / APP_PORT  >  APP_URL  >  built-in default
    """

    app_url: str = dataclasses.field(default_factory=lambda: env("APP_URL", ""))
    host: str = dataclasses.field(default_factory=lambda: env("APP_HOST", ""))
    port: int = dataclasses.field(default_factory=lambda: env("APP_PORT", 0))
    reload: bool = dataclasses.field(default_factory=lambda: env("APP_RELOAD", True))
    reload_dirs: list | None = None
    reload_excludes: list = dataclasses.field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
