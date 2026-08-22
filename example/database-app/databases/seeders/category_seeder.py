from fastapi_startkit.masoniteorm.seeders import Seeder
from app.models.category import Category


class CategorySeeder(Seeder):
    async def run(self):
        categories = [
            "Programming",
            "Web Development",
            "Data Science",
            "Design",
            "Business",
        ]
        for name in categories:
            await Category.first_or_create({"name": name})
