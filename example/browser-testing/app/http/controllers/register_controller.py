from fastapi.responses import RedirectResponse
from fastapi_startkit_auth import AsyncAuth

from app.http.requests.register_request import RegisterRequest
from app.models.user import User
from fastapi_startkit.inertia import Inertia
from fastapi_startkit.inertia.inertia import InertiaResponse
from fastapi_startkit.validation import Validated


async def create() -> InertiaResponse:
    return Inertia.render("Auth/Register", {})


async def store(data: Validated[RegisterRequest]) -> RedirectResponse:
    user = await User.create({"name": data.name, "email": data.email, "password": data.password})
    await AsyncAuth.login(user)
    return RedirectResponse("/dashboard", status_code=303)
