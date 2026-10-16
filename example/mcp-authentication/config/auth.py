from dataclasses import dataclass, field
from typing import Any

from fastapi_startkit.environment import env
from fastapi_startkit_auth import AuthConfig as BaseAuthConfig
from fastapi_startkit_auth import OAuth2Config, OAuthTokenConfig
from fastapi_startkit_auth.config import OAuth2Guard

from config.mcp import McpConfig


class AuthConfig(BaseAuthConfig):
    default = {"guard": "mcp"}
    providers = {"users": {"driver": "memory"}}

    @classmethod
    def get(cls, name: str, default: Any = None) -> Any:
        if name == "guards":
            return {"mcp": OAuth2Guard(provider="users", audience=McpConfig().resource)}
        return super().get(name, default)


@dataclass
class OAuthConfig(OAuth2Config):
    key: str | None = env("OAUTH2_KEY")
    issuer: str | None = env("APP_URL", "http://127.0.0.1:8000")
    resources: list[str] = field(default_factory=lambda: [McpConfig().resource])
    scopes: dict[str, str] = field(
        default_factory=lambda: {
            "notes:read": "Read your notes",
            "notes:write": "Create notes",
        }
    )
    default_scopes: list[str] = field(default_factory=lambda: ["notes:read"])
    grant_types: list[str] = field(default_factory=lambda: ["client_credentials"])
    tokens: OAuthTokenConfig = field(
        default_factory=lambda: OAuthTokenConfig(driver="database")
    )
