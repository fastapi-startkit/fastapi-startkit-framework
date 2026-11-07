from dataclasses import dataclass

from fastapi_startkit.configuration import Config
from fastapi_startkit.environment import env


@dataclass
class NotificationConfig(Config):
    table: str = env("NOTIFICATIONS_TABLE", "notifications")
    connection: str | None = env("DB_NOTIFICATIONS_CONNECTION", None, cast=False)


__all__ = ["NotificationConfig"]
