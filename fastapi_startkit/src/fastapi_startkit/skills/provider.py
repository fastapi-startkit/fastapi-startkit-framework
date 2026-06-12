"""SkillsServiceProvider — registers the skills module into the application."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.providers import Provider

_STUBS_DIR = Path(__file__).parent / "stubs"


class SkillsServiceProvider(Provider):
    """Service provider that bootstraps the skills module.

    Register it in your application::

        app = Application(
            providers=[
                ...,
                SkillsServiceProvider,
            ]
        )

    After booting, resolve the registry from the container::

        from fastapi_startkit.application import app
        registry = app().make("skills.registry")
        skills = registry.discover()

    Publish the starter ``core.html`` to your project with::

        artisan provider:publish --provider=skills
    """

    provider_key = "skills"

    def register(self) -> None:
        """Bind :class:`~fastapi_startkit.skills.SkillRegistry` into the container."""
        from fastapi_startkit.skills.registry import SkillRegistry

        self.app.bind("skills.registry", SkillRegistry(self.app))

    def boot(self) -> None:
        """Register commands and publishable resources."""
        from fastapi_startkit.skills.commands import SkillsSyncCommand, SkillsListCommand

        self.commands([SkillsSyncCommand, SkillsListCommand])

        # Publish the starter core.html → project/.ai/deployments/core.html
        self.publishes(
            {
                str(_STUBS_DIR / "core.html"): ".ai/deployments/core.html",
            },
            tag="skills",
        )
