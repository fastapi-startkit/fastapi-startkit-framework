import hashlib

from fastapi.exceptions import RequestValidationError

from app.http.schemas.auth import StudentRegistrationRequest
from app.models import User, Profile


async def register(request: StudentRegistrationRequest):
    existing_user = await User.where("email", request.email).first()
    if existing_user:
        raise RequestValidationError(
            errors=[
                {
                    "loc": ("body", "email"),
                    "msg": "Email already registered",
                    "type": "value_error",
                    "input": request.email,
                }
            ]
        )

    password = hashlib.md5(request.password.encode()).hexdigest()
    user = User(
        name=request.name,
        email=request.email,
        password=password,
        role="student",
    )
    await user.save()

    profile = Profile()
    profile.user_id = user.id
    await profile.save()

    return {"message": "Student registered successfully", "user_id": user.id}
