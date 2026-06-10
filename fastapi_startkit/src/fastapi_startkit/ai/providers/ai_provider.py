"""AIProvider — registers AI configuration into the service container."""

from __future__ import annotations

from fastapi_startkit.providers import Provider


class AIProvider(Provider):
    """Service provider that bootstraps the AI module.

    Registers :class:`~fastapi_startkit.ai.config.AIConfig` under the ``ai``
    key in the application container so it is accessible via ``Config.get('ai')``.

    Register it in your application::

        app = Application(providers=[AIProvider])
    """

    provider_key = "ai"

    def register(self) -> None:
        """Bind AIConfig into the container under the 'ai' key."""
        from fastapi_startkit.ai.config import AIConfig

        self.app.bind("ai", AIConfig())

    def boot(self) -> None:
        """Merge AI config into the shared Config store."""
        ai_config = self.app.make("ai")
        self.app.make("config").set("ai", ai_config)
