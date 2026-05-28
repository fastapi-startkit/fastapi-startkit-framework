from fastapi_startkit.masoniteorm.seeds import Seeder
from .category_seeder import CategorySeeder
from .user_seeder import UserSeeder
from .course_seeder import CourseSeeder
from .review_seeder import ReviewSeeder


class DatabaseSeeder(Seeder):
    async def run(self):
        await self.call(CategorySeeder)
        await self.call(UserSeeder)
        await self.call(CourseSeeder)
        await self.call(ReviewSeeder)
