from fastapi_startkit.masoniteorm.models import Model


class Account(Model):
    """Account Model."""

    __table__ = "accounts"

    id: int
    name: str
