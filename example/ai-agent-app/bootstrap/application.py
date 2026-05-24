from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.inertia import InertiaProvider
from fastapi_startkit.logging import LogProvider
from fastapi_startkit.vite import ViteProvider

from providers.fastapi_provider import FastAPIProvider

app: Application = Application(
    base_path=Path(__file__).parent.parent,
    providers=[
        LogProvider,
        FastAPIProvider,
        ViteProvider,
        InertiaProvider,
    ],
)
