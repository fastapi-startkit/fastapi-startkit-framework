import dataclasses
import os
from urllib.parse import urlparse

from fastapi_startkit.environment import env


def _parse_app_url() -> tuple[str | None, int | None]:
    """Parse APP_URL and return (hostname, port). Returns (None, None) if not set."""
    url = os.environ.get("APP_URL", "")
    if not url:
        return None, None
    # Ensure the URL has a scheme so urlparse works correctly
    if "://" not in url:
        url = f"http://{url}"
    parsed = urlparse(url)
    return parsed.hostname or None, parsed.port or None


def _default_host() -> str:
    """APP_HOST > APP_URL hostname > 127.0.0.1"""
    if os.environ.get("APP_HOST"):
        return env("APP_HOST", "127.0.0.1")
    host, _ = _parse_app_url()
    return host or "127.0.0.1"


def _default_port() -> int:
    """APP_PORT > APP_URL port > 8000"""
    if os.environ.get("APP_PORT"):
        return int(env("APP_PORT", 8000))
    _, port = _parse_app_url()
    return port or 8000


@dataclasses.dataclass
class FastAPIConfig:
    """Server configuration for the uvicorn/FastAPI serve command.

    All fields can be overridden via environment variables or by publishing a
    ``config/fastapi.py`` file in the application root.

    Resolution order for host and port:
    1. APP_HOST / APP_PORT (explicit env vars)
    2. APP_URL (parsed — e.g. http://myapp.com:8080)
    3. Hard-coded defaults (127.0.0.1 / 8000)
    """

    host: str = dataclasses.field(default_factory=_default_host)
    port: int = dataclasses.field(default_factory=_default_port)
    reload: bool = dataclasses.field(default_factory=lambda: env("APP_RELOAD", True))
    reload_dirs: list | None = None
    reload_excludes: list = dataclasses.field(
        default_factory=lambda: [
            "*.log",
            "tests/*",
            "node_modules/*",
        ]
    )
