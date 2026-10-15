from fastapi import HTTPException
import hashlib

from app.models.user import User
from app.models.profile import Profile
from app.http.schemas.auth import TeacherRegistrationRequest


class AuthController:
    @staticmethod
    async def register_teacher(data: TeacherRegistrationRequest):
        # Check if user exists
        existing_user = await User.where("email", data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        hashed_password = hashlib.md5(data.password.encode()).hexdigest()

        # Create user
        user = User(name=data.name, email=data.email, role="teacher")
        user.password = hashed_password
        await user.save()

        # Workaround for asyncpg insert bug in masoniteorm returning dict to primary key
        actual_user_id = user.id.get("id") if isinstance(user.id, dict) else user.id

        # Create teacher profile
        profile = Profile(
            bio=None,
            website=None,
            avatar_url=None,
            country=data.country,
            phone_number=data.phone_number,
            headline=data.headline,
            description=data.description,
            video_url=data.video_url,
            hourly_rate=data.hourly_rate,
            languages_spoken=data.languages_spoken,
            subjects=data.subjects,
        )
        profile.user_id = actual_user_id
        await profile.save()

        return {"message": "Teacher registered successfully", "user_id": actual_user_id}
