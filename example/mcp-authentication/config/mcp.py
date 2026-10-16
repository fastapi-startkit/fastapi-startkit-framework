from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class McpConfig(Config):
    app_url: str = env("APP_URL", "http://127.0.0.1:8000")
    path: str = "/mcp"
    scopes: dict[str, str] = field(
        default_factory=lambda: {
            "notes:read": "Read your notes",
            "notes:write": "Create notes",
        }
    )

    @property
    def resource(self) -> str:
        return f"{self.app_url}{self.path}"

    @property
    def resource_metadata_url(self) -> str:
        return f"{self.app_url}/.well-known/oauth-protected-resource{self.path}"
