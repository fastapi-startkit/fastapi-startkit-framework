from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from providers.fastapi_provider import FastAPIProvider
from config.fastapi import FastAPIConfig

app: Application = Application(
    base_path=str(Path.cwd()),  # This always gives path relative to the execution.
    providers=[
        LogProvider,
        (FastAPIProvider, FastAPIConfig),
    ],
)
