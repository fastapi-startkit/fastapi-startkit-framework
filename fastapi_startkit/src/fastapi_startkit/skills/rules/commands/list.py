"""rules:list — list all rules nested inside skill directories."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.console import Command


class RulesListCommand(Command):
    """List all rule files and their deployment status.

    Example usage::

        artisan rules:list
    """

    name = "rules:list"
    description = "List skill-nested rules and their AI agent sync status."

    def handle(self) -> int:
        from fastapi_startkit.skills.rules.registry import RulesRegistry

        registry: RulesRegistry = self.container.make("rules.registry")
        rules = registry.discover()

        if not rules:
            self.line("<comment>No rules found. Publish stubs first: artisan provider:publish --provider=skills</comment>")
            return 0

        base_path: Path = self.container.base_path

        self.line("")
        self.line(f"  <info>Found {len(rules)} rule(s):</info>")
        self.line("")

        header = f"  {'SKILL':<28} {'RULE':<25} {'CLAUDE':<10} {'GEMINI':<10}"
        self.line(header)
        self.line("  " + "-" * (len(header) - 2))

        for rule in rules:
            claude_dest = (
                base_path / ".claude" / "skills" / rule.skill_name / "rules" / f"{rule.name}.md"
            )
            claude_status = "synced" if claude_dest.exists() else "pending"
            gemini_status = self._gemini_status(base_path)
            self.line(
                f"  {rule.skill_name:<28} {rule.name:<25} {claude_status:<10} {gemini_status:<10}"
            )

        self.line("")
        return 0

    @staticmethod
    def _gemini_status(base_path: Path) -> str:
        gemini_md = base_path / "GEMINI.md"
        if not gemini_md.exists():
            return "pending"
        return "synced" if "<!-- rules:start -->" in gemini_md.read_text(encoding="utf-8") else "pending"
