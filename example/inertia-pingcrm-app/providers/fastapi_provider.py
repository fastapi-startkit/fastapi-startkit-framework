from pathlib import Path

from authentication.middlewares.auth import AuthMiddleware, NotAuthenticated
from fastapi import FastAPI, Request
from fastapi_startkit.fastapi import FastAPIProvider as BaseFastAPIProvider
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates


class FastAPIProvider(BaseFastAPIProvider):
    def register(self) -> None:
        fastapi = FastAPI(
            title="Vite Example",
            version="0.1.0",
        )
        self.app.use_fastapi(fastapi)

        templates_dir = Path(self.app.base_path) / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        self.app.bind("templates", templates)

    def boot(self) -> None:
        super().boot()

        inertia = self.app.make("inertia")
        inertia.share("app_name", "Inertia Demo")
        inertia.version("v1.0.0")
        inertia.share(
            "auth", lambda request: {"user": getattr(request.state, "user", None)}
        )
        inertia.share(
            "flash",
            lambda request: {
                "success": request.session.get("flash_success")
                if "session" in request.scope
                else None,
                "error": request.session.get("flash_error")
                if "session" in request.scope
                else None,
            },
        )
        inertia.share("errors", {})

        from routes.web import guest, auth

        self.app.include_router(guest)
        self.app.include_router(auth)
