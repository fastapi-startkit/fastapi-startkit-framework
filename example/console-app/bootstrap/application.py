from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from providers import ConsoleServiceProvider

app: Application = Application(
    base_path=Path(__file__).resolve().parent.parent,
    providers=[LogProvider, ConsoleServiceProvider],
)
