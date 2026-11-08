from fastapi_startkit_auth import AsyncAuth

from fastapi_startkit.inertia import Inertia
from fastapi_startkit.inertia.inertia import InertiaResponse


async def index() -> InertiaResponse:
    user = await AsyncAuth.user()
    return Inertia.render("Dashboard", {"user": {"name": user.name, "email": user.email}})
