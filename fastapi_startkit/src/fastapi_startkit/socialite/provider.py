from pathlib import Path
from typing import override

from fastapi_startkit.support import Provider

from .config import ServicesConfig
from .manager import SocialiteManager


class SocialiteProvider(Provider):
    provider_key = "services"

    @override
    def register(self) -> None:
        self.merge_config_from(self.resolve_config(ServicesConfig), self.provider_key)
        self.app.bind("socialite", SocialiteManager(self.app.make("config").get(self.provider_key, {})))

    @override
    def boot(self) -> None:
        directory = Path(__file__).resolve().parent
        self.publishes({directory / "config" / "__init__.py": "config/services.py"})
