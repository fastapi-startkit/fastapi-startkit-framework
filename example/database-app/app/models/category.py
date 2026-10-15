from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import HasMany, HasManyThrough

if TYPE_CHECKING:
    pass


class Category(Model):
    __table__ = "categories"

    name: str
    description: str | None

    courses = HasMany("Course")
    lessons = HasManyThrough(["Lesson", "Course"], "category_id", "course_id")
