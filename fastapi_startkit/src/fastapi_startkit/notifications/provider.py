from pathlib import Path
from typing import Any

from fastapi_startkit.support import Provider

from .channels import DatabaseChannel, MailChannel
from .config import NotificationConfig
from .manager import ChannelManager

MIGRATION = "2026_11_06_000000_create_notifications_table.py"


class NotificationProvider(Provider):
    provider_key = "notifications"

    def register(self) -> None:
        config = self.resolve_config(NotificationConfig)
        self.merge_config_from(config, self.provider_key)
        manager = ChannelManager(config)
        manager.extend("mail", lambda: MailChannel(lambda: self.require("mail", "MailProvider")))
        manager.extend("database", lambda: DatabaseChannel(lambda: self.connection(config), config["table"]))
        self.app.bind("notification", manager)

    def connection(self, config: dict[str, Any]) -> Any:
        return self.require("db", "DatabaseProvider").connection(config.get("connection"))

    def require(self, key: str, provider: str) -> Any:
        if not self.app.has(key):
            raise RuntimeError(f"Notifications through [{key}] require {provider} to be registered.")
        return self.app.make(key)

    def boot(self) -> None:
        directory = Path(__file__).resolve().parent
        self.publishes(
            {
                directory / "config" / "__init__.py": "config/notifications.py",
                directory / "migrations" / MIGRATION: f"databases/migrations/{MIGRATION}",
            }
        )
