from fastapi_startkit.fastapi import FastAPIProvider as BaseFastapiProvider
from routes.api import public


class FastAPIProvider(BaseFastapiProvider):
    def boot(self) -> None:
        super().boot()

        # Register routers
        self.app.include_router(public)
