from pathlib import Path

from fastapi import FastAPI
from starlette.templating import Jinja2Templates

from fastapi_startkit.fastapi import FastAPIProvider as BaseFastAPIProvider


class FastAPIProvider(BaseFastAPIProvider):
    def register(self) -> None:
        fastapi = FastAPI(
            title="Vite Example",
            version="0.1.0",
        )
        self.app.use_fastapi(fastapi)

        # Bind Jinja2Templates so ViteProvider can inject vite() globals into it.
        templates_dir = Path(self.app.base_path) / "templates"
        templates = Jinja2Templates(directory=str(templates_dir))
        self.app.bind("templates", templates)

    def boot(self) -> None:
        super().boot()

        from routes.web import web

        self.app.include_router(web)
