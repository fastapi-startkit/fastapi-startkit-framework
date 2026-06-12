"""RulesRegistry — discovers per-skill rule files nested inside each skill directory.

Rules live **inside** their parent skill, mirroring the Laravel Boost convention::

    .ai/fastapi-startkit/skill/
        fastapi-best-practices/
            SKILL.md
            rules/
                http-client.md
                validation.md
        orm-best-practices/
            SKILL.md
            rules/
                queries.md

Each rule is a plain Markdown file.  The rule **name** is the file stem
(``http-client.md`` → ``"http-client"``).  The owning skill is determined
from the parent directory name two levels up (``fastapi-best-practices``).

Optional YAML front-matter may supply an explicit ``name`` or ``description``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.application import Application

#: Root under which all skill (and nested rule) directories live.
SKILLS_BASE_PATH = Path(".ai") / "fastapi-startkit" / "skill"


@dataclass
class Rule:
    """A per-topic coding rule nested inside a skill directory."""

    name: str           # file stem, e.g. "http-client"
    skill_name: str     # owning skill directory name, e.g. "fastapi-best-practices"
    path: Path          # absolute path to the .md source file
    body: str = field(default="", repr=False)
    description: str = ""


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse optional YAML front-matter; return ``(meta, body)``."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    fm_text = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1:])

    try:
        import yaml  # type: ignore[import]
        meta = yaml.safe_load(fm_text) or {}
    except ModuleNotFoundError:
        meta = {}
        for line in lines[1:end_idx]:
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()

    return meta, body


class RulesRegistry:
    """Loads :class:`Rule` objects from nested ``rules/`` dirs inside each skill.

    Scan path: ``{base_path}/.ai/fastapi-startkit/skill/*/rules/*.md``

    Usage::

        from fastapi_startkit.application import app
        registry = app().make("rules.registry")
        rules = registry.discover()
        rules_for_skill = registry.for_skill("fastapi-best-practices")
    """

    def __init__(self, app: "Application") -> None:
        self._app = app
        self._rules: list[Rule] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def skills_base_path(self) -> Path:
        """Absolute path to the skill root (parent of all skill dirs)."""
        return Path(self._app.base_path) / SKILLS_BASE_PATH

    def discover(self) -> list[Rule]:
        """Return (and cache) all rules found across all skill directories."""
        if self._rules is not None:
            return self._rules

        base = self.skills_base_path
        if not base.is_dir():
            self._rules = []
            return self._rules

        self._rules = []
        for skill_dir in sorted(base.iterdir()):
            if not skill_dir.is_dir():
                continue
            rules_dir = skill_dir / "rules"
            if not rules_dir.is_dir():
                continue
            for md_file in sorted(rules_dir.glob("*.md")):
                rule = self._load(md_file, skill_name=skill_dir.name)
                if rule is not None:
                    self._rules.append(rule)

        return self._rules

    def for_skill(self, skill_name: str) -> list[Rule]:
        """Return all rules belonging to *skill_name*."""
        return [r for r in self.discover() if r.skill_name == skill_name]

    def get(self, name: str, skill_name: str | None = None) -> Rule | None:
        """Return the first :class:`Rule` matching *name*, optionally scoped to *skill_name*."""
        candidates = self.for_skill(skill_name) if skill_name else self.discover()
        return next((r for r in candidates if r.name == name), None)

    def reset(self) -> None:
        """Invalidate the discovery cache."""
        self._rules = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(md_file: Path, skill_name: str) -> Rule | None:
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            return None

        meta, body = _parse_frontmatter(text)
        name = (meta.get("name") or md_file.stem or "").strip()
        if not name:
            return None

        return Rule(
            name=name,
            skill_name=skill_name,
            path=md_file,
            body=body.strip() if body.strip() else text.strip(),
            description=(meta.get("description") or "").strip(),
        )
