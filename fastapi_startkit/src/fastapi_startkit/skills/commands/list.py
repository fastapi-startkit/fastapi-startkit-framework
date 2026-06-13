"""skills:list — list skills available from registered providers."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.console import Command


class SkillsListCommand(Command):
    """List all skills declared by the registered providers.

    For each skill the command shows:

    * provider key
    * skill name
    * description
    * sync status for Claude Code and Gemini CLI

    Example usage::

        artisan skills:list
    """

    name = "skills:list"
    description = "List skills declared by registered providers and their sync status."

    def handle(self) -> int:
        from fastapi_startkit.skills.registry import SkillRegistry

        registry: SkillRegistry = self.container.make("skills.registry")
        skills = registry.discover()

        if not skills:
            self.line("<comment>No skills found in any registered provider.</comment>")
            return 0

        base_path: Path = self.container.base_path

        self.line("")
        self.line(f"  <info>Found {len(skills)} skill(s):</info>")
        self.line("")

        header = f"  {'PROVIDER':<20} {'NAME':<25} {'CLAUDE':<10} {'GEMINI':<10}  DESCRIPTION"
        self.line(header)
        self.line("  " + "-" * (len(header) - 2))

        for skill in skills:
            claude_status = self._claude_status(skill.name, base_path)
            gemini_status = self._gemini_status(base_path)

            desc = skill.description[:50] + "…" if len(skill.description) > 50 else skill.description
            self.line(f"  {skill.provider_key:<20} {skill.name:<25} {claude_status:<10} {gemini_status:<10}  {desc}")

        self.line("")
        return 0

    # ------------------------------------------------------------------
    # Sync-status helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _claude_status(skill_name: str, base_path: Path) -> str:
        skill_file = base_path / ".claude" / "skills" / skill_name / "SKILL.md"
        return "synced" if skill_file.exists() else "pending"

    @staticmethod
    def _gemini_status(base_path: Path) -> str:
        gemini_md = base_path / "GEMINI.md"
        if not gemini_md.exists():
            return "pending"
        content = gemini_md.read_text(encoding="utf-8")
        return "synced" if "<!-- skills:start -->" in content else "pending"
