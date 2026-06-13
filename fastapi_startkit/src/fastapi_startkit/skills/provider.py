"""SkillsServiceProvider — registers skills and rules into the application."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.providers import Provider

_STUBS_DIR = Path(__file__).parent / "stubs"


class SkillsServiceProvider(Provider):
    """Service provider that bootstraps the skills and rules modules.

    Publish starter files with::

        artisan provider:publish --provider=skills

    This copies:
    - .ai/fastapi-startkit/fastapi-startkit/SKILL.md
    """

    provider_key = "skills"

    def register(self) -> None:
        from fastapi_startkit.skills.registry import SkillRegistry
        from fastapi_startkit.skills.rules.registry import RulesRegistry

        self.app.bind("skills.registry", SkillRegistry(self.app))
        self.app.bind("rules.registry", RulesRegistry(self.app))

    def boot(self) -> None:
        from fastapi_startkit.skills.commands import SkillsSyncCommand, SkillsListCommand
        from fastapi_startkit.skills.rules.commands import RulesSyncCommand, RulesListCommand

        self.commands(
            [
                SkillsSyncCommand,
                SkillsListCommand,
                RulesSyncCommand,
                RulesListCommand,
            ]
        )

        _skill_stub = _STUBS_DIR / ".ai" / "fastapi-startkit" / "fastapi-startkit"
        self.publishes(
            {
                str(_skill_stub / "SKILL.md"): ".ai/fastapi-startkit/fastapi-startkit/SKILL.md",
            },
            tag="skills",
        )
