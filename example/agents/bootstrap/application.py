from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.inertia import InertiaProvider
from fastapi_startkit.logging import LogProvider
from fastapi_startkit.skills import AISkillProvider
from fastapi_startkit.vite import ViteProvider
from fastapi_startkit.ai import AIProvider

from config.fastapi import FastAPIConfig
from config.logging import LoggingConfig
from config.vite import ViteConfig
from app.providers.fastapi_provider import FastapiProvider

app: Application = Application(
    base_path=Path(__file__).resolve().parent.parent,
    providers=[
        AISkillProvider,
        (LogProvider,LoggingConfig),
        (FastapiProvider, FastAPIConfig),
        AIProvider,
        (ViteProvider, ViteConfig),
        InertiaProvider,
    ],
)
