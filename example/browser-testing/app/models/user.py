from typing import Annotated

from app.casts.hashed import Hashed
from fastapi_startkit.masoniteorm.models import Model


class User(Model):
    __table__ = "users"
    __hidden__ = ["password"]

    name: str
    email: str
    password: Annotated[str, Hashed()]
