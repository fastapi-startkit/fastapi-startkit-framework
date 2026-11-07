from app.models.user import User
from fastapi_startkit.masoniteorm.seeders import Seeder


class DatabaseSeeder(Seeder):
    async def run(self):
        await User.create({"name": "Bedram Tamang", "email": "tmgbedu@gmail.com", "password": "password"})
