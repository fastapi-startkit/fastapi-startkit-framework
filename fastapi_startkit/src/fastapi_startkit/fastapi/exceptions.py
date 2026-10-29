from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class HTTPExceptionHandler:
    """
    The base exception handler for FastAPI applications.
    """

    def report(self, exc) -> None:
        from fastapi_startkit.container import Container

        status = self.http_status(exc)
        if status is not None and status < 500:
            return

        cast("Application", Container.instance()).exception_manager.report_exception(exc)

    @staticmethod
    def http_status(exc) -> int | None:
        from starlette.exceptions import HTTPException

        from fastapi_startkit.exceptions import HttpException

        if isinstance(exc, HTTPException):
            return exc.status_code
        if isinstance(exc, HttpException):
            return exc.get_status()
        return None

    async def render(self, request, exc):
        import traceback
        from fastapi.exception_handlers import http_exception_handler
        from fastapi.responses import JSONResponse
        from starlette.exceptions import HTTPException

        from fastapi_startkit.container import Container
        from fastapi_startkit.exceptions import HttpException

        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)

        if isinstance(exc, HttpException):
            return await http_exception_handler(
                request, HTTPException(exc.get_status(), exc.get_response(), headers=exc.get_headers())
            )

        app = cast("Application", Container.instance())
        if app.is_debug():
            tb = exc.__traceback__
            frames = traceback.extract_tb(tb)
            content = {
                "message": str(exc),
                "exception": f"{type(exc).__module__}.{type(exc).__qualname__}",
                "file": frames[-1].filename if frames else None,
                "line": frames[-1].lineno if frames else None,
                "trace": [{"file": f.filename, "line": f.lineno, "function": f.name} for f in frames],
            }
        else:
            content = {"message": "Server Error"}

        return JSONResponse(status_code=500, content=content)


class ValidationExceptionHandler:
    """
    Handles RequestValidationError and ValidationException with content negotiation.

    JSON requests (API clients) receive a 422 Unprocessable Entity response.
    Non-JSON requests (browser/Inertia) have errors flashed to the session
    and are redirected back to the referring page.
    """

    def report(self, exc) -> None:
        pass

    async def render(self, request, exc):
        from fastapi_startkit.inertia.constant import Header

        accept = request.headers.get("accept", "")
        content_type = request.headers.get("content-type", "")

        wants_json = "application/json" in accept or content_type.startswith("application/json")

        from fastapi_startkit.exceptions import ValidationException
        from fastapi_startkit.validation.message_bag import MessageBag

        bag = exc.bag if isinstance(exc, ValidationException) else MessageBag.from_errors(exc.errors(), skip=1)
        errors = bag.messages

        if request.headers.get(Header.INERTIA):
            return self.redirect_back_with_errors(request, errors)

        if wants_json:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=422, content=bag.to_dict())

        if "session" in request.scope:
            request.session["errors"] = errors

        from starlette.responses import RedirectResponse

        from fastapi_startkit.fastapi.referer import same_origin_referer

        return RedirectResponse(url=same_origin_referer(request), status_code=303)

    @staticmethod
    def redirect_back_with_errors(request, errors: dict):
        from fastapi_startkit.fastapi.referer import same_origin_referer
        from fastapi_startkit.inertia import session
        from fastapi_startkit.inertia.constant import Header
        from fastapi_startkit.inertia.redirect import InertiaRedirect

        session.put_errors(request, errors, request.headers.get(Header.ERROR_BAG) or session.DEFAULT_BAG)
        return InertiaRedirect(same_origin_referer(request), status_code=303)
