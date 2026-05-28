import uuid
from pathlib import Path
from typing import Optional


from fastapi import Request, Depends, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi_startkit.inertia import Inertia
from fastapi_startkit.storage import Storage
from app.models.User import User
from app.http.requests.profile import ProfileUpdateRequest


async def save_photo(photo: Optional[UploadFile]) -> Optional[str]:
    if photo is None or not photo.filename:
        return None
    if not photo.content_type or not photo.content_type.startswith("image/"):
        return None
    ext = Path(photo.filename).suffix.lower() or ".jpg"
    filename = f"photos/{uuid.uuid4().hex}{ext}"
    Storage.disk("s3").put(filename, await photo.read())
    return filename


async def edit(request: Request):
    user = await User.find(request.state.user["id"])
    photo_url = f"/images/{user.photo_path}" if user.photo_path else None
    return Inertia.render(
        "Profile/Edit",
        {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "photo": photo_url,
                "password": "",
            }
        },
    )


async def update(
    request: Request,
    form: ProfileUpdateRequest = Depends(),
    photo: Optional[UploadFile] = File(default=None),
):
    user = await User.find(request.state.user["id"])

    photo_path = await save_photo(photo)

    update_data = form.validated()
    if photo_path:
        update_data["photo_path"] = photo_path

    await user.update(update_data)
    return RedirectResponse(url="/profile", status_code=303)
