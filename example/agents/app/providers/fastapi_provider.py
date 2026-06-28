from fastapi_startkit.fastapi import FastAPIProvider as BaseFastAPIProvider
from fastapi.templating import Jinja2Templates


class FastapiProvider(BaseFastAPIProvider):
    def boot(self):
        templates_dir = self.app.use_base_path("resources/templates")
        self.app.bind("templates", Jinja2Templates(directory=str(templates_dir)))

        super().boot()
        from routes.api import api

        self.app.fastapi.include_router(api)
