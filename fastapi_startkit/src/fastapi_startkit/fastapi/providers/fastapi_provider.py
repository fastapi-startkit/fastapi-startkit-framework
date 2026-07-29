from fastapi_startkit.fastapi.exceptions import HTTPExceptionHandler, ValidationExceptionHandler
from fastapi import FastAPI

from fastapi_startkit.fastapi.commands import ServeCommand
from fastapi_startkit.fastapi.config import FastAPIConfig
from fastapi_startkit.fastapi.middleware import REQUEST_ID_HEADER, RequestLifecycleMiddleware
from fastapi_startkit.support import Provider


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
        self.app.add_middleware(RequestLifecycleMiddleware)

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
            response = await exception_manager.handle(exc, {"request": request})

            # Starlette promotes the bare-Exception handler onto ServerErrorMiddleware,
            # which sits outside RequestLifecycleMiddleware — so that middleware never
            # sees the response built here and can't stamp the header itself. Stamp it
            # here instead, for every exception path this handler covers.
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                response.headers.setdefault(REQUEST_ID_HEADER, request_id)

            return response

        # FastAPI registers its own handlers for these two types internally,
        # so they must be overridden explicitly
        self.app.fastapi.add_exception_handler(HTTPException, handler)
        self.app.fastapi.add_exception_handler(RequestValidationError, handler)
        self.app.fastapi.add_exception_handler(Exception, handler)
