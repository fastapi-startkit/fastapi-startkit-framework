from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm.models import Model
from fastapi_startkit.masoniteorm import BelongsTo

if TYPE_CHECKING:
    from app.models.user import User


class Profile(Model):
    __table__ = "profiles"

    bio: str | None
    website: str | None
    avatar_url: str | None
    country: str | None
    phone_number: str | None
    headline: str | None
    description: str | None
    video_url: str | None
    hourly_rate: int | None
    languages_spoken: dict | list | None
    subjects: dict | list | None

    user = BelongsTo("User")
