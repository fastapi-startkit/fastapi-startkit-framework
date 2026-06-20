from fastapi import FastAPI

from fastapi_startkit.fastapi import FastAPIProvider as BaseFastAPIProvider


class FastAPIProvider(BaseFastAPIProvider):
    def register(self) -> None:
        fastapi = FastAPI(
            title="Vite Example",
            version="0.1.0",
        )
        self.app.use_fastapi(fastapi)

    def boot(self) -> None:
        super().boot()

        from routes.web import web

        self.app.include_router(web)
