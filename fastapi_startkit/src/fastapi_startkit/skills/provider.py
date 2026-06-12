"""SkillsServiceProvider — registers the skills module into the application."""

from __future__ import annotations

from fastapi_startkit.providers import Provider


class SkillsServiceProvider(Provider):
    """Service provider that bootstraps the skills module.

    Register it in your application::

        app = Application(
            providers=[
                ...,
                SkillsServiceProvider,
            ]
        )

    After booting the application you can resolve the registry from the
    container::

        from fastapi_startkit.application import app
        registry = app().make("skills.registry")
        skills = registry.discover()
    """

    provider_key = "skills"

    def register(self) -> None:
        """Bind a :class:`~fastapi_startkit.skills.SkillRegistry` into the container."""
        from fastapi_startkit.skills.registry import SkillRegistry

        # Bind as a callable so the container resolves it lazily on first make()
        self.app.bind("skills.registry", SkillRegistry(self.app))

    def boot(self) -> None:
        """Register the skills:sync and skills:list artisan commands."""
        from fastapi_startkit.skills.commands import SkillsSyncCommand, SkillsListCommand

        self.commands([SkillsSyncCommand, SkillsListCommand])
