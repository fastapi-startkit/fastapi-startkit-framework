from fastapi_startkit.masoniteorm.seeds import Seeder
from app.models.course import Course
from app.models.review import Review


class ReviewSeeder(Seeder):
    async def run(self):
        courses = await Course.all()

        reviews_by_title = {
            "Python for Beginners": [
                "Great intro course, very clear explanations.",
                "Loved the pace — perfect for someone new to Python.",
            ],
            "FastAPI in Practice": [
                "Hands-on and practical. Exactly what I needed.",
                "Covered everything from routing to database — highly recommended.",
            ],
            "Intro to Data Science": [
                "Solid foundation. The Pandas section was especially useful.",
                "Good course overall, could use more real-world examples.",
            ],
        }

        for course in courses:
            contents = reviews_by_title.get(course.title, [])
            for content in contents:
                await Review.first_or_create(
                    {
                        "reviewable_type": "courses",
                        "reviewable_id": course.id,
                        "content": content,
                    }
                )
