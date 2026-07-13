from fastapi_startkit.masoniteorm.seeders import Seeder
from app.models.category import Category
from app.models.course import Course
from app.models.user import User
from app.models.lesson import Lesson


class CourseSeeder(Seeder):
    async def run(self):
        instructor = await User.where("email", "instructor@example.com").first()
        programming = await Category.where("name", "Programming").first()
        web_dev = await Category.where("name", "Web Development").first()
        data_science = await Category.where("name", "Data Science").first()

        courses = [
            {
                "title": "Python for Beginners",
                "instructor_id": instructor.id,
                "category_id": programming.id,
            },
            {
                "title": "FastAPI in Practice",
                "instructor_id": instructor.id,
                "category_id": web_dev.id,
            },
            {
                "title": "Intro to Data Science",
                "instructor_id": instructor.id,
                "category_id": data_science.id,
            },
        ]

        lesson_map = {
            "Python for Beginners": [
                "Variables and Types",
                "Control Flow",
                "Functions",
                "Classes and OOP",
            ],
            "FastAPI in Practice": [
                "Project Setup",
                "Routing and Endpoints",
                "Request Validation",
                "Database Integration",
            ],
            "Intro to Data Science": [
                "NumPy Basics",
                "Pandas DataFrames",
                "Data Visualisation",
                "Building a Model",
            ],
        }

        for data in courses:
            course, _ = await Course.first_or_create({"title": data["title"]}, data)
            for title in lesson_map[data["title"]]:
                await Lesson.first_or_create(
                    {"title": title, "course_id": course.id}
                )