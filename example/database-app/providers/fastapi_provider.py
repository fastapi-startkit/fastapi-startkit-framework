from fastapi_startkit.fastapi import FastAPIProvider


class FastAPIServiceProvider(FastAPIProvider):
    def boot(self) -> None:
        super().boot()

        # Register routers
        from routes.student import router as student
        from routes.api import public

        self.app.include_router(student)
        self.app.include_router(public)
