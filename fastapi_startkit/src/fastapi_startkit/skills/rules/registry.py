"""RulesRegistry — discovers per-topic rule files from ``rules/``.

Rules are individual Markdown files that contain detailed coding guidelines::

    rules/
        http-client.md          ← HTTP client best practices
        orm-queries.md          ← ORM / database query rules
        validation.md           ← Request validation rules
        error-handling.md       ← Error handling patterns

Each file is plain Markdown.  The rule **name** is derived from the file stem
(``http-client.md`` → ``http-client``).  An optional YAML front-matter block
may supply an explicit name or description, but it is not required.

Rules are referenced from skill files (e.g. the Quick Reference section of
``.ai/fastapi-startkit/skill/fastapi-best-practices/SKILL.md``) and are also
deployed individually to every configured AI agent target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.application import Application

#: Location of rule files relative to the project root.
RULES_BASE_PATH = Path("rules")


@dataclass
class Rule:
    """A single per-topic coding rule loaded from ``rules/<name>.md``."""

    name: str           # derived from file stem, e.g. "http-client"
    path: Path          # absolute path to the .md source file
    body: str = field(default="", repr=False)   # full markdown content
    description: str = ""                        # from frontmatter if present


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse optional YAML front-matter and return ``(meta, body)``."""
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
    """Loads :class:`Rule` objects from ``{base_path}/rules/*.md``.

    Usage::

        from fastapi_startkit.application import app
        registry = app().make("rules.registry")
        rules = registry.discover()
    """

    def __init__(self, app: "Application") -> None:
        self._app = app
        self._rules: list[Rule] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def rules_base_path(self) -> Path:
        """Absolute path to the ``rules/`` directory."""
        return Path(self._app.base_path) / RULES_BASE_PATH

    def discover(self) -> list[Rule]:
        """Return (and cache) all rules found in ``rules/``."""
        if self._rules is not None:
            return self._rules

        base = self.rules_base_path
        if not base.is_dir():
            self._rules = []
            return self._rules

        self._rules = []
        for md_file in sorted(base.glob("*.md")):
            rule = self._load(md_file)
            if rule is not None:
                self._rules.append(rule)

        return self._rules

    def get(self, name: str) -> Rule | None:
        """Return the :class:`Rule` with *name* (file stem), or *None*."""
        return next((r for r in self.discover() if r.name == name), None)

    def reset(self) -> None:
        """Invalidate the discovery cache."""
        self._rules = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load(md_file: Path) -> Rule | None:
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
            path=md_file,
            body=body.strip() if body.strip() else text.strip(),
            description=(meta.get("description") or "").strip(),
        )
