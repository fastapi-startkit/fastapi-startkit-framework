from pathlib import Path

from fastapi_startkit import Application
from fastapi_startkit.fastapi import FastAPIProvider
from fastapi_startkit.masoniteorm.providers import DatabaseProvider
from fastapi_startkit.mcp import McpProvider
from fastapi_startkit_auth import AuthOAuth2Provider, AuthProvider

from config.auth import OAuthConfig, auth_config
from config.mcp import McpConfig
from providers.mcp_provider import McpServiceProvider

app: Application = Application(
    base_path=Path(__file__).parent.parent,
    providers=[
        DatabaseProvider,
        FastAPIProvider,
        (AuthProvider, auth_config),
        (AuthOAuth2Provider, OAuthConfig),
        McpProvider,
        (McpServiceProvider, McpConfig),
    ],
)
