import dataclasses

from fastapi_startkit.environment import env


@dataclasses.dataclass
class FastAPIConfig:
    app_url: str = dataclasses.field(default_factory=lambda: env("APP_URL", "http://127.0.0.1:8000"))
    reload: bool = dataclasses.field(default_factory=lambda: env("APP_RELOAD", True))
    # uvicorn WebSocket backend: auto, none, websockets, websockets-sansio, wsproto.
    # 'auto' never requires the optional 'websockets' package unless a WS connection is opened.
    ws: str = dataclasses.field(default_factory=lambda: env("APP_WS", "auto"))
    reload_dirs: list | None = None
    reload_excludes: list = dataclasses.field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
