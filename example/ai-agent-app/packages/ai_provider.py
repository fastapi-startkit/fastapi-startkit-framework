from fastapi_startkit.providers import ServiceProvider

from packages.config import AIConfig


class AIProvider(ServiceProvider):
    def register(self) -> None:
        config = self.app.make("config")
        config.set("ai", AIConfig())
