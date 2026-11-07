from pathlib import Path

from fastapi_startkit.support import Provider

from .config import MailConfig
from .manager import MailManager


class MailProvider(Provider):
    provider_key = "mail"

    def register(self) -> None:
        config = self.resolve_config(MailConfig)
        self.merge_config_from(config, self.provider_key)
        self.app.bind("mail", MailManager(config))

    def boot(self) -> None:
        directory = Path(__file__).resolve().parent
        self.publishes({directory / "config" / "__init__.py": "config/mail.py"})
