from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia
from app.models.User import User


async def create():
    return Inertia.render("Auth/Login", {})


async def store(request: Request):
    form = await request.json()
    email = form.get("email")
    password = form.get("password")

    user = await User.where("email", email).first()
    if user and user.password == password:
        request.session["user_id"] = user.id
        return RedirectResponse(url="/", status_code=303)

    return Inertia.render(
        "Auth/Login",
        {"errors": {"email": "These credentials do not match our records."}},
    )


async def destroy(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
