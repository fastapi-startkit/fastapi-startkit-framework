"""skills:sync — sync provider skills to one or more agent targets."""

from __future__ import annotations

from cleo.helpers import option

from fastapi_startkit.console import Command


class SkillsSyncCommand(Command):
    """Sync provider skills into Claude Code / Gemini CLI skill files.

    Example usage::

        artisan skills:sync
        artisan skills:sync --target=claude
        artisan skills:sync --target=gemini --prune
    """

    name = "skills:sync"
    description = "Sync provider-declared skills to AI agent skill files."

    options = [
        option(
            "target",
            "t",
            flag=False,
            default="all",
            description="Target adapter: claude | gemini | all (default: all)",
        ),
        option(
            "prune",
            None,
            flag=True,
            description="Remove skill files that are no longer declared by any provider.",
        ),
    ]

    def handle(self) -> int:
        from fastapi_startkit.skills.registry import SkillRegistry

        registry: SkillRegistry = self.container.make("skills.registry")
        skills = registry.discover()

        target = (self.option("target") or "all").lower()
        do_prune = bool(self.option("prune"))
        base_path = self.container.base_path

        adapters = self._resolve_adapters(target, base_path)

        if not adapters:
            self.line(f"<error>Unknown target '{target}'. Use: claude, gemini, all.</error>")
            return 1

        if not skills:
            self.line(
                "<comment>No skills found. Publish stubs first: artisan provider:publish --provider=skills</comment>"
            )
            return 0

        self.line(f"<info>Found {len(skills)} skill(s). Syncing to: {target}…</info>")
        self.line("")

        for adapter in adapters:
            messages = adapter.render(skills)
            for msg in messages:
                self.line(f"  {msg}")

            if do_prune:
                prune_messages = adapter.prune(skills)
                for msg in prune_messages:
                    self.line(f"  {msg}")

        self.line("")
        self.line("<info>Done.</info>")
        return 0

    @staticmethod
    def _resolve_adapters(target: str, base_path) -> list:
        from fastapi_startkit.skills.adapters import ClaudeAdapter, GeminiAdapter

        all_adapters = {
            "claude": ClaudeAdapter,
            "gemini": GeminiAdapter,
        }

        if target == "all":
            return [cls(base_path) for cls in all_adapters.values()]

        cls = all_adapters.get(target)
        return [cls(base_path)] if cls else []
