from typing import Optional
from fastapi_startkit.masoniteorm import Model


class User(Model):
    """User Model."""

    __table__ = "users"
    __hidden__ = ["password", "remember_token"]

    id: int
    account_id: int
    first_name: str
    last_name: str
    email: str
    password: Optional[str]
    owner: bool
    photo_path: Optional[str]
    remember_token: Optional[str]

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
