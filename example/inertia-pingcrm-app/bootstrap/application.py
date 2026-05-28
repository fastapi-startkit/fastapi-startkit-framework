from pathlib import Path

from config.database import DatabaseConfig
from config.storage import StorageConfig
from providers.fastapi_provider import FastAPIProvider
from starlette.middleware.trustedhost import TrustedHostMiddleware

from starlette.middleware.sessions import SessionMiddleware

from authentication.middlewares.auth import AuthMiddleware, NotAuthenticated
from fastapi_startkit import Application
from fastapi_startkit.exceptions import ExceptionHandler as BaseHandler
from fastapi_startkit.inertia import InertiaProvider
from fastapi_startkit.logging import LogProvider
from fastapi_startkit.masoniteorm import DatabaseProvider
from fastapi_startkit.storage.providers.provider import StorageProvider
from fastapi_startkit.vite import ViteProvider
from starlette.responses import RedirectResponse


class ExceptionHandler(BaseHandler):
    def register(self):
        self.register_render(
            NotAuthenticated,
            lambda request, exc: RedirectResponse(url="/login", status_code=303),
        )


app: Application = Application(
    base_path=str(Path.cwd()),
    providers=[
        LogProvider,
        (DatabaseProvider, DatabaseConfig),
        (StorageProvider, StorageConfig),
        FastAPIProvider,
        ViteProvider,
        InertiaProvider,
    ],
    exception_handler=ExceptionHandler,
)


app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key="...")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
