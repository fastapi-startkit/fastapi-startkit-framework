from fastapi_startkit.fastapi import FastAPIProvider


class FastapiProvider(FastAPIProvider):
    def boot(self):
        super().boot()
        from fastapi_startkit_auth import AuthenticationException

        from app.exceptions.unauthenticated import unauthenticated
        from routes.api import router
        from routes.web import authenticated
        from routes.web import router as web_router

        self.app.fastapi.include_router(router.router)
        self.app.fastapi.include_router(web_router.router)
        self.app.fastapi.include_router(authenticated.router)
        self.app.fastapi.add_exception_handler(AuthenticationException, unauthenticated)
