from fastapi_startkit.inertia import Inertia


async def index():
    return Inertia.render("Reports/Index", {})
