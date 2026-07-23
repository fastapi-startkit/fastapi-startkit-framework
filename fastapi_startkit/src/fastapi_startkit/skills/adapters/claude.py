"""ClaudeAdapter — renders skills into ``.claude/skills/<name>/SKILL.md``."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from fastapi_startkit.skills.registry import Skill
from .base import BaseAdapter


class ClaudeAdapter(BaseAdapter):
    """Writes canonical skills into Claude Code's skill directory.

    Each skill is rendered as ``.claude/skills/<skill-name>/SKILL.md`` with a
    YAML front-matter block followed by the original body.  Publishing follows
    the same rules as ``provider:publish``: a missing file is written, an
    existing file is left untouched unless ``force`` is set or the caller
    confirms the overwrite.
    """

    name = "claude"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        skills: Sequence[Skill],
        force: bool = False,
        confirm: Callable[..., bool] | None = None,
    ) -> list[str]:
        messages: list[str] = []
        for skill in skills:
            dest = self._skill_path(skill.name)
            rel = f".claude/skills/{skill.name}/SKILL.md"
            content = self._build_content(skill)

            if dest.exists() and not force:
                if not self._confirm_overwrite(confirm, rel):
                    messages.append(f"[claude] Skipped <comment>{rel}</comment> (already exists)")
                    continue
                verb = "Overwrote"
            else:
                verb = "Overwrote" if dest.exists() else "Published"

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            messages.append(f"[claude] {verb} <info>{rel}</info>")
        return messages

    @staticmethod
    def _confirm_overwrite(confirm: Callable[..., bool] | None, rel: str) -> bool:
        """Ask the caller whether to overwrite *rel*; default to no."""
        if confirm is None:
            return False
        return bool(confirm(f"  <comment>{rel}</comment> already exists. Overwrite?", default=False))

    def prune(self, skills: Sequence[Skill]) -> list[str]:
        """Remove ``.claude/skills/<name>/`` dirs not represented in *skills*."""
        messages: list[str] = []
        known_names = {s.name for s in skills}
        skills_root = self.base_path / ".claude" / "skills"
        if not skills_root.is_dir():
            return messages

        for child in sorted(skills_root.iterdir()):
            if child.is_dir() and child.name not in known_names:
                import shutil

                shutil.rmtree(child)
                messages.append(f"[claude] Pruned .claude/skills/{child.name}/")
        return messages

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _skill_path(self, skill_name: str) -> Path:
        return self.base_path / ".claude" / "skills" / skill_name / "SKILL.md"

    @staticmethod
    def _build_content(skill: Skill) -> str:
        """Render the SKILL.md content for *skill*."""
        lines = ["---", f"name: {skill.name}", f"description: {skill.description}", "---"]
        if skill.body:
            lines.append("")
            lines.append(skill.body)
        lines.append("")
        return "\n".join(lines)
