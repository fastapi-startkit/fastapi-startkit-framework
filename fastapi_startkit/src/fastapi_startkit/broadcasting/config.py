from dataclasses import dataclass, field
from fastapi_startkit.environment import env


@dataclass
class BroadcastingConfig:
    default: str = field(default_factory=lambda: env("BROADCAST_DRIVER", "log"))

    connections: dict = field(
        default_factory=lambda: {
            "reverb": {
                "driver": "reverb",
                "key": env("REVERB_APP_KEY", "local"),
                "secret": env("REVERB_APP_SECRET", "secret"),
                "app_id": env("REVERB_APP_ID", "1"),
                "host": env("REVERB_HOST", "0.0.0.0"),
                "port": int(env("REVERB_PORT", 8080)),
                "scheme": env("REVERB_SCHEME", "http"),
            },
            "log": {
                "driver": "log",
            },
        }
    )
