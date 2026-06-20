from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import BelongsTo, MorphMany

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.review import Review


class Lesson(Model):
    __table__ = "lessons"

    title: str

    course = BelongsTo("Course")
    reviews = MorphMany("Review", "reviewable_type", "reviewable_id")
