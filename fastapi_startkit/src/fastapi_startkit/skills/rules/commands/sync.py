"""rules:sync — sync per-topic rule files to AI agent targets."""

from __future__ import annotations

from cleo.helpers import option

from fastapi_startkit.console import Command


class RulesSyncCommand(Command):
    """Deploy ``rules/*.md`` files to AI agent rule directories.

    Example usage::

        artisan rules:sync
        artisan rules:sync --target=claude
        artisan rules:sync --target=gemini --prune
    """

    name = "rules:sync"
    description = "Sync rules/*.md files to AI agent rule directories."

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
            description="Remove rule files that no longer exist in rules/.",
        ),
    ]

    def handle(self) -> int:
        from fastapi_startkit.skills.rules.registry import RulesRegistry

        registry: RulesRegistry = self.container.make("rules.registry")
        rules = registry.discover()

        target = (self.option("target") or "all").lower()
        do_prune = bool(self.option("prune"))
        base_path = self.container.base_path

        adapters = self._resolve_adapters(target, base_path)

        if not adapters:
            self.line(f"<error>Unknown target '{target}'. Use: claude, gemini, all.</error>")
            return 1

        if not rules:
            self.line("<comment>No rules found in rules/. Create rules/*.md files first.</comment>")
            return 0

        self.line(f"<info>Found {len(rules)} rule(s). Syncing to: {target}…</info>")
        self.line("")

        for adapter in adapters:
            for msg in adapter.render(rules):
                self.line(f"  {msg}")
            if do_prune:
                for msg in adapter.prune(rules):
                    self.line(f"  {msg}")

        self.line("")
        self.line("<info>Done.</info>")
        return 0

    @staticmethod
    def _resolve_adapters(target: str, base_path) -> list:
        from fastapi_startkit.skills.rules.adapters import ClaudeRulesAdapter, GeminiRulesAdapter

        all_adapters = {"claude": ClaudeRulesAdapter, "gemini": GeminiRulesAdapter}
        if target == "all":
            return [cls(base_path) for cls in all_adapters.values()]
        cls = all_adapters.get(target)
        return [cls(base_path)] if cls else []
