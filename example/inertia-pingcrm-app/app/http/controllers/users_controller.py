import uuid
from pathlib import Path
from typing import Optional

from fastapi import Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia
from fastapi_startkit.storage import Storage
from app.models.User import User


async def _save_photo(photo: Optional[UploadFile]) -> Optional[str]:
    """Save an UploadFile to the public disk and return its public URL path, or None."""
    if photo is None or not photo.filename:
        return None
    if not photo.content_type or not photo.content_type.startswith("image/"):
        return None

    ext = Path(photo.filename).suffix.lower() or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"

    Storage.disk("public").put(filename, await photo.read())

    return f"/storage/{filename}"


async def index():
    users = await User.query().limit(10).get()
    return Inertia.render(
        "Users/Index",
        {
            "users": {
                "data": [
                    {
                        "id": u.id,
                        "name": f"{u.first_name} {u.last_name}",
                        "email": u.email,
                        "owner": u.owner,
                        "photo": u.photo_path,
                        "deleted_at": None,
                    }
                    for u in users
                ],
                "links": {"first": None, "last": None, "prev": None, "next": None},
                "meta": {
                    "current_page": 1,
                    "last_page": 1,
                    "per_page": 10,
                    "from": 1,
                    "to": len(users),
                    "total": len(users),
                    "path": "/users",
                    "links": [],
                },
            }
        },
    )


async def create():
    return Inertia.render("Users/Create", {})


async def store(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(default=""),
    owner: str = Form(default="0"),
    photo: Optional[UploadFile] = File(default=None),
):
    photo_path = await _save_photo(photo)

    user_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "password": password,
        "owner": owner == "1",
    }
    if photo_path:
        user_data["photo_path"] = photo_path

    await User.create(user_data)
    return RedirectResponse(url="/users", status_code=303)


async def edit(user: int):
    u = await User.find(user)
    return Inertia.render(
        "Users/Edit",
        {
            "user": {
                "id": u.id,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "owner": u.owner,
                "photo": u.photo_path,
                "password": "",
                "deleted_at": None,
            }
        },
    )


async def update(
    request: Request,
    user: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(default=""),
    owner: str = Form(default="0"),
    photo: Optional[UploadFile] = File(default=None),
):
    u = await User.find(user)

    photo_path = await _save_photo(photo)

    update_data = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "owner": owner == "1",
    }
    if password:
        update_data["password"] = password
    if photo_path:
        update_data["photo_path"] = photo_path

    await u.update(update_data)
    return RedirectResponse(url=f"/users/{user}/edit", status_code=303)


async def destroy(user: int):
    return RedirectResponse(url="/users", status_code=303)


async def restore(user: int):
    return RedirectResponse(url="/users", status_code=303)
