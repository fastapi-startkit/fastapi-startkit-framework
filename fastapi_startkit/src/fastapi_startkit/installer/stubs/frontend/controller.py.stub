from fastapi_startkit.inertia import Inertia
from fastapi_startkit.inertia.inertia import InertiaResponse


class HomeController:
    async def index(self) -> InertiaResponse:
        return Inertia.render("Home")

    async def health(self):
        return {"status": "ok"}
