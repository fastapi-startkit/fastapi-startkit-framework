"""AIProvider — registers AI configuration into the service container."""

from __future__ import annotations

from fastapi_startkit.providers import Provider


class AIProvider(Provider):
    provider_key = "ai"

    def register(self) -> None:
        from fastapi_startkit.ai import AIConfig

        config = self.resolve_config(AIConfig)
        self.merge_config_from(config, self.provider_key)

    def boot(self) -> None:
        pass
