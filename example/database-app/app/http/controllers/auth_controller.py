from fastapi import HTTPException
import hashlib

from app.models.user import User
from app.models.profile import Profile
from app.http.schemas.auth import StudentRegistrationRequest, TeacherRegistrationRequest


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
        user = User()
        user.name = data.name
        user.email = data.email
        user.password = hashed_password
        user.role = "teacher"
        await user.save()

        # Workaround for asyncpg insert bug in masoniteorm returning dict to primary key
        actual_user_id = user.id.get("id") if isinstance(user.id, dict) else user.id

        # Create teacher profile
        profile = Profile()
        profile.user_id = actual_user_id
        profile.country = data.country
        profile.phone_number = data.phone_number
        profile.headline = data.headline
        profile.description = data.description
        profile.video_url = data.video_url
        profile.hourly_rate = data.hourly_rate
        import json

        profile.languages_spoken = json.dumps(data.languages_spoken)
        profile.subjects = json.dumps(data.subjects)
        await profile.save()

        return {"message": "Teacher registered successfully", "user_id": actual_user_id}
