from pathlib import Path

from starlette.middleware.sessions import SessionMiddleware

from fastapi_startkit import Application
from fastapi_startkit.logging import LogProvider
from config.app import AppConfig
from config.logging import LoggingConfig
from fastapi_startkit.masoniteorm import DatabaseProvider
from config.database import DatabaseConfig
from config.fastapi import FastAPIConfig
from providers.fastapi_provider import FastapiProvider
from fastapi_startkit.inertia import InertiaProvider
from fastapi_startkit.vite import ViteProvider
from config.vite import ViteConfig
from fastapi_startkit.environment import env
from fastapi_startkit_auth import AuthProvider, AuthSessionProvider
from config.auth import AuthConfig, SessionConfig

app = Application(
    base_path=Path(__file__).resolve().parent.parent,
    config=AppConfig,
    providers=[
        (LogProvider, LoggingConfig),
        (DatabaseProvider, DatabaseConfig),
        (FastapiProvider, FastAPIConfig),
        (ViteProvider, ViteConfig),
        InertiaProvider,
        (AuthProvider, AuthConfig),
        (AuthSessionProvider, SessionConfig),
    ],
)

app.add_middleware(SessionMiddleware, secret_key=env("APP_KEY", "browser-testing-insecure-key"))
