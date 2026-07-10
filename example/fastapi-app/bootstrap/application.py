from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from providers.fastapi_provider import FastAPIProvider
from config.fastapi import FastAPIConfig
from config.logging import LoggingConfig

app: Application = Application(
    base_path=str(Path(__file__).parent.parent),  # App root, resolved relative to this file (bootstrap/ -> root).
    providers=[
        (LogProvider, LoggingConfig),
        (FastAPIProvider, FastAPIConfig),
    ],
)
