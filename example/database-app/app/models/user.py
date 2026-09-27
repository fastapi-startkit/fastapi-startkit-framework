from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import HasMany, HasOne, BelongsToMany

if TYPE_CHECKING:
    from app.models.profile import Profile
    from app.models.course import Course


class User(Model):
    __table__ = "users"

    name: str
    email: str
    role: str

    profile = HasOne("Profile")
    courses = BelongsToMany(
        "Course",
        local_foreign_key="user_id",
        other_foreign_key="course_id",
        table="course_user",
        with_timestamps=True,
        with_fields=["progress", "completed_at"],
    )
