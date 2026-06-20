from pathlib import Path

from fastapi_startkit.application import Application
from fastapi_startkit.logging import LogProvider
from fastapi_startkit.vite import ViteProvider

# from config.vite import ViteConfig
from providers.fastapi_provider import FastAPIProvider

app: Application = Application(
    base_path=Path(__file__).resolve().parent.parent,
    providers=[
        LogProvider,
        FastAPIProvider,
        ViteProvider,
    ],
)
