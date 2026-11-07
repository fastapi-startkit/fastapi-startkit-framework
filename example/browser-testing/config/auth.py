from dataclasses import dataclass

from fastapi_startkit.environment import env
from fastapi_startkit_auth import AuthConfig as BaseAuthConfig
from fastapi_startkit_auth import SessionConfig as BaseSessionConfig
from fastapi_startkit_auth.config import SessionGuard

from app.models.user import User


class AuthConfig(BaseAuthConfig):
    default = {"guard": "web"}
    guards = {"web": SessionGuard(provider="users")}
    providers = {"users": {"driver": "async_model", "model": User}}


@dataclass
class SessionConfig(BaseSessionConfig):
    driver: str = "database"
    secure: bool = env("SESSION_SECURE_COOKIE", True)
