from typing import TYPE_CHECKING

from fastapi_startkit.support import Str
from fastapi_startkit.support.dataclass import Dataclass

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class Provider:
    provider_key: str = None

    def __init__(self, application: "Application", config: dict = None):
        self.app: "Application" = application
        self.config = config or {}

        if self.provider_key is None:
            self.provider_key = str(Str.of(self.__class__.__name__).trim("ServiceProvider").trim("Provider").slugify())

    def register(self) -> None:
        pass

    def boot(self) -> None:
        pass

    def resolve_config(self, default) -> dict:
        user_config = Dataclass.to_dict(self.config)
        default_config = Dataclass.to_dict(default())

        return {**default_config, **user_config}

    def merge_config_from(self, source: str | dict, provider_key: str) -> None:
        self.app.make("config").merge_with(provider_key, source)

    def publishes(self, resources: dict, tag: str = None) -> None:
        self.app.published_resources.setdefault(self.provider_key, {}).update(resources)

    def commands(self, commands: list) -> None:
        self.app.add_commands(commands)
