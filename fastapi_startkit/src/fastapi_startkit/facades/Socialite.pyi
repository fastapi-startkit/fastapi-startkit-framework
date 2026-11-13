from collections.abc import Mapping
from typing import Any

from fastapi_startkit.socialite import Provider, SocialiteManager
from fastapi_startkit.socialite.manager import ProviderFactory

class Socialite:
    @staticmethod
    def driver(name: str) -> Provider: ...
    @staticmethod
    def extend(driver: str, factory: ProviderFactory) -> SocialiteManager: ...
    @staticmethod
    def build_provider(provider: type[Provider], config: Mapping[str, Any], name: str = "") -> Provider: ...
