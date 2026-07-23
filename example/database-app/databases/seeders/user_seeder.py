from fastapi_startkit.masoniteorm.seeders import Seeder
from app.models.user import User
from app.models.profile import Profile


class UserSeeder(Seeder):
    async def run(self):
        users = [
            {
                "email": "instructor@example.com",
                "name": "Jane Smith",
                "password": "secret",
                "role": "instructor",
                "profile": {
                    "bio": "Senior software engineer and educator.",
                    "headline": "Python & FastAPI Instructor",
                    "country": "US",
                    "hourly_rate": 80,
                    "languages_spoken": ["English"],
                    "subjects": ["Python", "FastAPI", "Data Science"],
                },
            },
            {
                "email": "john@example.com",
                "name": "John Doe",
                "password": "secret",
                "role": "student",
                "profile": {
                    "bio": "Aspiring developer learning Python.",
                    "country": "UK",
                    "languages_spoken": ["English"],
                },
            },
            {
                "email": "alice@example.com",
                "name": "Alice Johnson",
                "password": "secret",
                "role": "student",
                "profile": {
                    "bio": "Data enthusiast transitioning into tech.",
                    "country": "CA",
                    "languages_spoken": ["English", "French"],
                },
            },
        ]

        for data in users:
            profile_data = data.pop("profile")
            user = await User.first_or_create({"email": data["email"]}, data)
            await Profile.first_or_create(
                {"user_id": user.id}, {"user_id": user.id, **profile_data}
            )
