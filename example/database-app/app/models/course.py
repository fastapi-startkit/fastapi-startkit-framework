from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import BelongsTo, HasMany, BelongsToMany, MorphMany

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.lesson import Lesson
    from app.models.user import User
    from app.models.review import Review


class Course(Model):
    __table__ = "courses"

    title: str
    description: str | None
    price: int

    category = BelongsTo("Category")
    lessons = HasMany("Lesson")
    students = BelongsToMany(
        "User", 
        local_foreign_key="course_id", 
        other_foreign_key="user_id", 
        table="course_user",
        with_timestamps=True,
        with_fields=["progress", "completed_at"]
    )
    reviews = MorphMany("Review", "reviewable_type", "reviewable_id")
