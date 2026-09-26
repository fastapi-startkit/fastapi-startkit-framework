from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from config.fastapi import FastAPIConfig
from providers.fastapi_provider import FastAPIProvider
from providers.queue_provider import QueueProvider
from providers.console_provider import ConsoleProvider

app: Application = Application(
    base_path=str(Path.cwd()),
    providers=[
        LogProvider,
        QueueProvider,
        (FastAPIProvider, FastAPIConfig),
        ConsoleProvider,
    ],
)
