from typing import Any

from ..user import SocialiteUser
from .abstract import Provider


class GoogleProvider(Provider):
    default_scopes = ("openid", "profile", "email")
    scope_separator = " "

    def get_auth_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/auth"

    def get_token_url(self) -> str:
        return "https://www.googleapis.com/oauth2/v4/token"

    async def get_user_by_token(self, token: str) -> dict[str, Any]:
        return await self.request_json(
            "GET",
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        )

    def map_user_to_object(self, user: dict[str, Any]) -> SocialiteUser:
        return SocialiteUser(
            id=str(user["sub"]),
            nickname=user.get("nickname"),
            name=user.get("name"),
            email=user.get("email"),
            avatar=user.get("picture"),
            raw=user,
        )
