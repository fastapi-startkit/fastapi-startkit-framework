import dataclasses
from urllib.parse import urlparse

from fastapi_startkit.environment import env


def _parse_app_url(component: str):
    """Extract host or port from APP_URL. Returns None if APP_URL is not set or the component is absent."""
    raw = env("APP_URL", "")
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    return parsed.hostname if component == "host" else parsed.port


@dataclasses.dataclass
class FastAPIConfig:
    """Server configuration for the uvicorn/FastAPI serve command.

    All fields can be overridden via environment variables or by publishing a
    ``config/fastapi.py`` file in the application root.

    Host and port resolution order:
    APP_HOST / APP_PORT  →  APP_URL  →  127.0.0.1 / 8000
    """

    host: str = dataclasses.field(
        default_factory=lambda: env("APP_HOST") or _parse_app_url("host") or "127.0.0.1"
    )
    port: int = dataclasses.field(
        default_factory=lambda: env("APP_PORT") or _parse_app_url("port") or 8000
    )
    reload: bool = dataclasses.field(default_factory=lambda: env("APP_RELOAD", True))
    reload_dirs: list | None = None
    reload_excludes: list = dataclasses.field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
