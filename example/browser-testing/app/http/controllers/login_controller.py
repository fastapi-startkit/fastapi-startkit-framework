from fastapi.responses import RedirectResponse
from fastapi_startkit_auth import AsyncAuth

from app.http.requests.login_request import LoginRequest
from fastapi_startkit.inertia import Inertia
from fastapi_startkit.inertia.inertia import InertiaResponse
from fastapi_startkit.validation import Validated


async def create() -> InertiaResponse:
    return Inertia.render("Auth/Login", {})


async def store(data: Validated[LoginRequest]) -> RedirectResponse:
    if not await AsyncAuth.attempt({"email": data.email, "password": data.password}):
        return Inertia.back_with_errors({"email": "These credentials do not match our records."})
    return RedirectResponse("/dashboard", status_code=303)


async def destroy() -> RedirectResponse:
    await AsyncAuth.logout()
    return RedirectResponse("/login", status_code=303)
