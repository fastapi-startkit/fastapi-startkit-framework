from dataclasses import dataclass, field

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class ReverbConnectionConfig(Config):
    driver: str = "reverb"
    key: str = env("REVERB_APP_KEY", "local")
    secret: str = env("REVERB_APP_SECRET", "secret")
    app_id: str = env("REVERB_APP_ID", "1")
    host: str = env("REVERB_HOST", "0.0.0.0")
    port: int = env("REVERB_PORT", 8080)
    scheme: str = env("REVERB_SCHEME", "http")


@dataclass
class LogConnectionConfig(Config):
    driver: str = "log"


@dataclass
class BroadcastingConfig(Config):
    default: str = env("BROADCAST_DRIVER", "log")

    connections: dict[str, ReverbConnectionConfig | LogConnectionConfig] = field(
        default_factory=lambda: {
            "reverb": ReverbConnectionConfig(),
            "log": LogConnectionConfig(),
        }
    )
