from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit_auth import OAuth2Config, OAuthTokenConfig
from fastapi_startkit_auth.config import OAuth2Guard

from config.mcp import McpConfig


def auth_config() -> dict:
    return {
        "default": {"guard": "mcp"},
        "guards": {"mcp": OAuth2Guard(provider="users", audience=McpConfig().resource)},
        "providers": {"users": {"driver": "memory"}},
    }


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
