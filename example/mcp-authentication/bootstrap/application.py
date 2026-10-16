from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.masoniteorm.providers import DatabaseProvider
from fastapi_startkit_auth import AuthOAuth2Provider, AuthProvider

from config.auth import AuthConfig, OAuthConfig
from config.mcp import McpConfig
from providers.mcp_provider import McpServiceProvider

app: Application = Application(
    base_path=Path(__file__).parent.parent,
    providers=[
        DatabaseProvider,
        FastAPIProvider,
        (AuthProvider, AuthConfig),
        (AuthOAuth2Provider, OAuthConfig),
        (McpServiceProvider, McpConfig),
    ],
)
