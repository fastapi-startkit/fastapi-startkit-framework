class HTTPExceptionHandler:
    """
    The base exception handler for FastAPI applications.
    """

    async def render(self, request, exc):
        import traceback
        from fastapi.responses import JSONResponse
        from fastapi_startkit.container import Container

        app = Container.instance()
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
    Handles RequestValidationError with content negotiation.

    JSON requests (API clients) receive a 422 Unprocessable Entity response.
    Non-JSON requests (browser/Inertia) have errors flashed to the session
    and are redirected back to the referring page.
    """

    def report(self, exc) -> None:
        pass

    async def render(self, request, exc):
        accept = request.headers.get("accept", "")
        content_type = request.headers.get("content-type", "")

        wants_json = "application/json" in accept or content_type.startswith("application/json")

        errors = {}
        for err in exc.errors():
            field = ".".join(str(x) for x in err["loc"][1:])
            errors.setdefault(field, []).append(err["msg"])

        if wants_json:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=422, content={"errors": errors})

        if "session" in request.scope:
            request.session["errors"] = errors

        from starlette.responses import RedirectResponse

        return RedirectResponse(
            url=request.headers.get("referer", "/"),
            status_code=303,
        )
