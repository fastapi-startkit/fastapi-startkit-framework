from collections.abc import Callable, Mapping
from typing import Any, Self

import httpx

from .exceptions import DriverMissingConfigurationException, SocialiteException
from .providers import GoogleProvider, Provider

ProviderFactory = Callable[[dict[str, Any]], Provider]

REQUIRED_KEYS = {"client_id": "CLIENT_ID", "client_secret": "CLIENT_SECRET", "redirect": "REDIRECT_URI"}


class SocialiteManager:
    def __init__(self, services: Mapping[str, Any], transport: httpx.AsyncBaseTransport | None = None):
        self.services = services
        self.transport = transport
        self._creators: dict[str, ProviderFactory] = {
            "google": lambda config: self.build_provider(GoogleProvider, config, "google"),
        }

    def driver(self, name: str) -> Provider:
        if name not in self._creators:
            raise SocialiteException(f"Socialite driver [{name}] is not supported.")
        return self._creators[name](self.config_for(name))

    def config_for(self, name: str) -> dict[str, Any]:
        return dict(self.services.get(name) or {})

    def build_provider(self, provider: type[Provider], config: Mapping[str, Any], name: str = "") -> Provider:
        missing = [key for key in REQUIRED_KEYS if not config.get(key)]
        if missing:
            label = name or provider.__name__
            hints = ", ".join(f"{key} ({label.upper()}_{REQUIRED_KEYS[key]})" for key in missing)
            raise DriverMissingConfigurationException(f"Missing configuration for Socialite driver [{label}]: {hints}.")
        return provider(config["client_id"], config["client_secret"], config["redirect"], transport=self.transport)

    def extend(self, driver: str, factory: ProviderFactory) -> Self:
        self._creators[driver] = factory
        return self
