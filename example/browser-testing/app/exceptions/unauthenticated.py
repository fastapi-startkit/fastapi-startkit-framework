from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi_startkit_auth import AuthenticationException


def wants_page(request: Request) -> bool:
    return "x-inertia" in request.headers or "text/html" in request.headers.get("accept", "")


async def unauthenticated(request: Request, exception: AuthenticationException) -> Response:
    if wants_page(request):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(
        exception.to_dict(),
        status_code=exception.status_code,
        headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
    )
