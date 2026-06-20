from fastapi_startkit.fastapi.exceptions import HTTPExceptionHandler, ValidationExceptionHandler
from fastapi import FastAPI

from fastapi_startkit.fastapi.commands import ServeCommand
from fastapi_startkit.fastapi.config import FastAPIConfig
from fastapi_startkit.providers import Provider


class FastAPIProvider(Provider):
    provider_key = "fastapi"

    def register(self) -> None:
        """Create a FastAPI instance and register routers."""
        config = self.resolve_config(FastAPIConfig)
        self.merge_config_from(config, self.provider_key)

        fastapi = FastAPI(
            title="Jobins AI Agent (LangChain)",
            version="1.0.0",
        )

        self.app.use_fastapi(fastapi)

    def boot(self):
        import os

        self.commands([ServeCommand])
        self._register_exception_handlers()

        source = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config/fastapi.py"))
        self.publishes({source: "config/fastapi.py"})

    def _register_exception_handlers(self):
        """Wire exception_manager as a catch-all handler for all exceptions."""
        from fastapi import HTTPException
        from fastapi.exceptions import RequestValidationError

        exception_manager = self.app.exception_manager
        exception_manager.register_handler(Exception, HTTPExceptionHandler())
        exception_manager.register_handler(HTTPException, HTTPExceptionHandler())
        exception_manager.register_handler(RequestValidationError, ValidationExceptionHandler())

        async def handler(request, exc):
            return await exception_manager.handle(exc, {"request": request})

        # FastAPI registers its own handlers for these two types internally,
        # so they must be overridden explicitly
        self.app.fastapi.add_exception_handler(HTTPException, handler)
        self.app.fastapi.add_exception_handler(RequestValidationError, handler)
        self.app.fastapi.add_exception_handler(Exception, handler)
