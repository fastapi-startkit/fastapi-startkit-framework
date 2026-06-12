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
    - .ai/fastapi-startkit/skill/fastapi-best-practices/SKILL.md
    - rules/http-client.md
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

        self.commands([
            SkillsSyncCommand,
            SkillsListCommand,
            RulesSyncCommand,
            RulesListCommand,
        ])

        self.publishes(
            {
                str(_STUBS_DIR / ".ai" / "fastapi-startkit" / "skill" / "fastapi-best-practices" / "SKILL.md"):
                    ".ai/fastapi-startkit/skill/fastapi-best-practices/SKILL.md",
                str(_STUBS_DIR / "rules" / "http-client.md"):
                    "rules/http-client.md",
            },
            tag="skills",
        )
