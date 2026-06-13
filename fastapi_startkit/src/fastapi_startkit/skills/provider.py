from __future__ import annotations

from fastapi_startkit.providers import Provider


class AISkillProvider(Provider):
    provider_key = "ai_skill"

    def register(self) -> None:
        from fastapi_startkit.skills.registry import SkillRegistry

        self.app.bind(f"{self.provider_key}.skills.registry", SkillRegistry(self.app))

    def boot(self) -> None:
        from fastapi_startkit.skills.commands import SkillsCommand

        self.commands([SkillsCommand])
