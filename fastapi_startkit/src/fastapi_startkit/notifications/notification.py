from typing import Any

BROADCAST_EVENT = "Illuminate\\Notifications\\Events\\BroadcastNotificationCreated"


class Notification:
    id: str | None = None
    mailer: str | None = None

    def via(self, notifiable: Any) -> list[str]:
        return []

    def to_array(self, notifiable: Any) -> dict[str, Any]:
        return {}

    def broadcast_as(self) -> str:
        return BROADCAST_EVENT

    def broadcast_type(self) -> str:
        return type(self).__name__
