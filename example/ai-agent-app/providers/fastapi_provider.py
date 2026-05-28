from pathlib import Path

from fastapi_startkit.fastapi import FastAPIProvider as BaseFastAPIProvider
from starlette.templating import Jinja2Templates


class FastAPIProvider(BaseFastAPIProvider):
    def register(self) -> None:
        super().register()

        templates_dir = Path(self.app.base_path) / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        self.app.bind("templates", templates)

    def boot(self) -> None:
        super().boot()

        inertia = self.app.make("inertia")
        inertia.share("app_name", "AI Agent App")
        inertia.version("1.0.0")

        from routes.web import router

        self.app.include_router(router)
