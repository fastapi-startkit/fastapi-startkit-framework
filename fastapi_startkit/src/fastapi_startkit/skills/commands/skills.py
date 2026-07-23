"""ai:skills — list or sync provider-declared AI skills.

Examples::

    artisan ai:skills --list
    artisan ai:skills --sync
    artisan ai:skills --sync --target=claude --prune
"""

from __future__ import annotations

from cleo.helpers import option

from fastapi_startkit.console import Command


class SkillsCommand(Command):
    name = "ai:skills"
    description = "List or sync provider-declared AI skills."

    options = [
        option("list", "l", flag=True, description="List providers that declare skills (default)."),
        option("sync", "s", flag=True, description="Publish skills and sync them to AI agents."),
        option(
            "target",
            "t",
            flag=False,
            description="Sync target: claude | gemini | all. Prompts if omitted.",
        ),
        option(
            "prune",
            None,
            flag=True,
            description="Remove skill files no longer declared by any provider.",
        ),
        option(
            "force",
            "f",
            flag=True,
            description="Overwrite existing files without prompting.",
        ),
    ]

    def handle(self) -> int:
        from fastapi_startkit.skills.registry import SkillRegistry

        registry: SkillRegistry = self.container.make("ai_skill.skills.registry")

        # --target / --prune only make sense when syncing, so they imply --sync.
        if self.option("sync") or self.option("prune") or self.option("target"):
            return self._sync(registry)

        return self._list(registry)

    def _list(self, registry) -> int:
        providers = registry.get_providers()

        if providers.is_empty():
            self.line("<comment>No skills found in any registered provider.</comment>")
            return 0

        self.info("Skill(s) found for the following provider(s):")
        for index, provider_key in enumerate(providers, start=1):
            self.info(f"{index}. {provider_key}")
        return 0

    def _sync(self, registry) -> int:
        choices = ["all", "claude", "gemini"]
        target = self.option("target")
        if not target:
            answer = self.choice("Which agent do you want to publish for?", choices, default=0)
            # Interactive returns the value; non-interactive returns the default index.
            target = choices[answer] if isinstance(answer, int) else answer
        target = target.lower()
        prune = bool(self.option("prune"))
        force = bool(self.option("force"))

        for message in registry.publish(target=target, prune=prune, force=force, confirm=self.confirm):
            self.line(f"  {message}")
        return 0
