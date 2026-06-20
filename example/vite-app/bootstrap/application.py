from pathlib import Path

from fastapi_startkit.application import Application
from fastapi_startkit.logging import LogProvider
from fastapi_startkit.vite import ViteProvider

from providers.fastapi_provider import FastAPIProvider

app: Application = Application(
    base_path=Path(__file__).resolve().parent.parent,
    providers=[
        LogProvider,
        FastAPIProvider,
        # ViteProvider auto-binds a Jinja2Templates engine (with the vite()
        # globals injected) at the configured templates directory.
        (ViteProvider, {"templates_directory": "templates"}),
    ],
)
