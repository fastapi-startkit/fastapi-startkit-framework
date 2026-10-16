from dataclasses import dataclass

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class McpConfig(Config):
    app_url: str = env("APP_URL", "http://127.0.0.1:8000")
    path: str = "/mcp"

    @property
    def resource(self) -> str:
        return f"{self.app_url}{self.path}"

    @property
    def resource_metadata_url(self) -> str:
        return f"{self.app_url}/.well-known/oauth-protected-resource{self.path}"
