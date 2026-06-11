import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig:
    """Server configuration for the uvicorn/FastAPI serve command.

    All fields are raw environment values — no parsing or defaults applied here.
    Resolution logic (APP_HOST / APP_PORT → APP_URL → 127.0.0.1 / 8000)
    lives in ServeCommand.
    """

    host: str | None = dataclasses.field(default_factory=lambda: env("APP_HOST"))
    port: int | None = dataclasses.field(default_factory=lambda: env("APP_PORT"))
    app_url: str | None = dataclasses.field(default_factory=lambda: env("APP_URL"))
    reload: bool = dataclasses.field(default_factory=lambda: env("APP_RELOAD", True))
    reload_dirs: list | None = None
    reload_excludes: list = dataclasses.field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
