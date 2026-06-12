"""SkillRegistry — discovers canonical skills from ``.ai/fastapi-startkit/skill/``.

Skills follow the same convention as Laravel Boost::

    .ai/fastapi-startkit/skill/
        fastapi-best-practices/
            SKILL.md        <- YAML frontmatter (name, description) + markdown body

Running ``artisan skills:sync`` deploys skills to every configured AI agent target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.application import Application

#: Base directory for framework skills (relative to project root).
SKILLS_BASE_PATH = Path(".ai") / "fastapi-startkit" / "skill"


@dataclass
class Skill:
    """Canonical skill metadata parsed from a SKILL.md file."""

    name: str
    description: str
    path: Path
    provider_key: str = "fastapi-startkit"
    body: str = field(default="", repr=False)
    metadata: dict = field(default_factory=dict, repr=False)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML front-matter. Returns (meta_dict, body_str)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    fm_text = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1:])

    try:
        import yaml
        meta = yaml.safe_load(fm_text) or {}
    except ModuleNotFoundError:
        meta = {}
        for line in lines[1:end_idx]:
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()

    return meta, body


class SkillRegistry:
    """Loads Skill objects from .ai/fastapi-startkit/skill/*/SKILL.md."""

    def __init__(self, app: "Application") -> None:
        self._app = app
        self._skills: list[Skill] | None = None

    @property
    def skills_base_path(self) -> Path:
        return Path(self._app.base_path) / SKILLS_BASE_PATH

    def discover(self) -> list[Skill]:
        if self._skills is not None:
            return self._skills

        base = self.skills_base_path
        if not base.is_dir():
            self._skills = []
            return self._skills

        self._skills = []
        for skill_md in sorted(base.rglob("SKILL.md")):
            skill = self._load(skill_md)
            if skill is not None:
                self._skills.append(skill)

        return self._skills

    def get(self, name: str) -> "Skill | None":
        return next((s for s in self.discover() if s.name == name), None)

    def reset(self) -> None:
        self._skills = None

    @staticmethod
    def _load(skill_md: Path) -> "Skill | None":
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            return None

        meta, body = _parse_frontmatter(text)
        name = (meta.get("name") or skill_md.parent.name or "").strip()
        if not name:
            return None

        description = (meta.get("description") or "").strip()
        extra = {k: v for k, v in meta.items() if k not in ("name", "description")}
        return Skill(
            name=name,
            description=description,
            path=skill_md,
            body=body.strip(),
            metadata=extra,
        )
