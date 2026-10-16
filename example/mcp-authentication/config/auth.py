from fastapi_startkit_auth import OAuth2Config, OAuthClientsConfig, OAuthTokensConfig
from fastapi_startkit_auth.config import OAuth2Guard

from config.mcp import McpConfig


def auth_config() -> dict:
    return {
        "default": {"guard": "mcp"},
        "guards": {"mcp": OAuth2Guard(provider="users", audience=McpConfig().resource)},
        "providers": {"users": {"driver": "memory"}},
    }


def oauth2_config() -> OAuth2Config:
    mcp = McpConfig()
    return OAuth2Config(
        key=mcp.oauth2_key,
        issuer=mcp.app_url,
        resources=[mcp.resource],
        scopes=mcp.scopes,
        default_scopes=["notes:read"],
        grant_types=["client_credentials"],
        tokens=OAuthTokensConfig(store="database"),
        clients=OAuthClientsConfig(store="database"),
    )
