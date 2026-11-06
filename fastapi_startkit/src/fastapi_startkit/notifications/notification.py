from typing import Any


class Notification:
    id: str | None = None
    mailer: str | None = None

    def via(self, notifiable: Any) -> list[str]:
        return []

    def to_array(self, notifiable: Any) -> dict[str, Any]:
        return {}
