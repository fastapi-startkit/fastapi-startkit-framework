from fastapi_startkit.inertia import Inertia
from fastapi_startkit.inertia.inertia import InertiaResponse


async def index() -> InertiaResponse:
    return Inertia.render("Home")


async def health():
    return {"status": "ok"}
