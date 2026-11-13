from dataclasses import dataclass, field
from typing import Any


@dataclass
class SocialiteUser:
    id: str
    nickname: str | None = None
    name: str | None = None
    email: str | None = None
    avatar: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    approved_scopes: list[str] = field(default_factory=list)
