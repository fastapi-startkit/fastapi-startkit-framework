"""ClaudeAdapter — renders skills into ``.claude/skills/<name>/SKILL.md``."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi_startkit.skills.registry import Skill
from .base import BaseAdapter


class ClaudeAdapter(BaseAdapter):
    """Writes canonical skills into Claude Code's skill directory.

    Each skill is rendered as ``.claude/skills/<skill-name>/SKILL.md`` with a
    YAML front-matter block followed by the original body.  Writes are
    idempotent — the file is only (over)written when its content would change.
    """

    name = "claude"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, skills: Sequence[Skill]) -> list[str]:
        messages: list[str] = []
        for skill in skills:
            dest = self._skill_path(skill.name)
            content = self._build_content(skill)
            written = self._write_idempotent(dest, content)
            verb = "Synced" if written else "Unchanged"
            messages.append(f"[claude] {verb} .claude/skills/{skill.name}/SKILL.md")
        return messages

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

    @staticmethod
    def _write_idempotent(path: Path, content: str) -> bool:
        """Write *content* to *path* only if it differs.

        Returns *True* when the file was (re)written, *False* when unchanged.
        """
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
