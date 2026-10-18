from typing import TYPE_CHECKING

from fastapi_startkit.masoniteorm import HasMany
from fastapi_startkit.masoniteorm.models import Model

if TYPE_CHECKING:
    from .message import Message  # noqa: F401


class Thread(Model):
    __table__ = "threads"
    __primary_key__ = "id"
    __incrementing__ = False  # id is the string conversation key, not auto-increment

    id: str
    title: str | None

    messages = HasMany["Message"](local_key="id", foreign_key="thread_id")
