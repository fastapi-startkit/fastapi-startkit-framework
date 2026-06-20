from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import HasMany, HasManyThrough

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.lesson import Lesson


class Category(Model):
    __table__ = "categories"

    name: str
    description: str | None

    courses = HasMany("Course")
    lessons = HasManyThrough(["Lesson", "Course"], "category_id", "course_id")
