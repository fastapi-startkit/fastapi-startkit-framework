from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class GoogleServiceConfig(Config):
    client_id: str | None = env("GOOGLE_CLIENT_ID", None, cast=False)
    client_secret: str | None = env("GOOGLE_CLIENT_SECRET", None, cast=False)
    redirect: str | None = env("GOOGLE_REDIRECT_URI", None, cast=False)


@dataclass
class ServicesConfig(Config):
    google: GoogleServiceConfig = field(default_factory=GoogleServiceConfig)


__all__ = ["GoogleServiceConfig", "ServicesConfig"]
