"""rules:list — list all rules found in rules/ and their sync status."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.console import Command


class RulesListCommand(Command):
    """List all rule files in ``rules/`` and their deployment status.

    Example usage::

        artisan rules:list
    """

    name = "rules:list"
    description = "List rules/*.md files and their AI agent sync status."

    def handle(self) -> int:
        from fastapi_startkit.skills.rules.registry import RulesRegistry

        registry: RulesRegistry = self.container.make("rules.registry")
        rules = registry.discover()

        if not rules:
            self.line("<comment>No rules found in rules/. Create rules/*.md files first.</comment>")
            return 0

        base_path: Path = self.container.base_path

        self.line("")
        self.line(f"  <info>Found {len(rules)} rule(s) in rules/:</info>")
        self.line("")

        header = f"  {'NAME':<30} {'CLAUDE':<10} {'GEMINI':<10}  PATH"
        self.line(header)
        self.line("  " + "-" * (len(header) - 2))

        for rule in rules:
            claude_status = "synced" if (base_path / ".claude" / "rules" / f"{rule.name}.md").exists() else "pending"
            gemini_status = self._gemini_status(base_path)
            rel = rule.path.relative_to(base_path) if rule.path.is_absolute() else rule.path
            self.line(f"  {rule.name:<30} {claude_status:<10} {gemini_status:<10}  {rel}")

        self.line("")
        return 0

    @staticmethod
    def _gemini_status(base_path: Path) -> str:
        gemini_md = base_path / "GEMINI.md"
        if not gemini_md.exists():
            return "pending"
        return "synced" if "<!-- rules:start -->" in gemini_md.read_text(encoding="utf-8") else "pending"
