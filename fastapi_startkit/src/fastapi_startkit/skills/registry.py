"""SkillRegistry — discovers canonical skills from registered providers.

Each provider can expose skills by placing a ``skills/`` directory next to its
``provider.py`` file.  Every ``SKILL.md`` inside that directory is read for
YAML front-matter that must declare at minimum ``name`` and ``description``.

Example layout::

    my_package/
        provider.py
        skills/
            my-skill/
                SKILL.md   ← name: my-skill / description: …

"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


@dataclass
class Skill:
    """Canonical skill metadata collected from a provider's skills/ directory."""

    name: str
    description: str
    path: Path
    provider_key: str = ""

    # Raw markdown body (everything after the YAML front-matter block)
    body: str = field(default="", repr=False)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML front-matter from *text*.

    Returns ``(meta_dict, body_str)`` where *meta_dict* holds the YAML keys and
    *body_str* is the remainder of the file after the closing ``---`` fence.
    Returns ``({}, text)`` if no front-matter block is found.
    """
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

    try:
        import yaml  # type: ignore[import]
    except ModuleNotFoundError:
        # Minimal fallback: parse simple "key: value" pairs
        meta: dict = {}
        for line in lines[1:end_idx]:
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
        body = "".join(lines[end_idx + 1 :])
        return meta, body

    meta = yaml.safe_load("".join(lines[1:end_idx])) or {}
    body = "".join(lines[end_idx + 1 :])
    return meta, body


class SkillRegistry:
    """Collects :class:`Skill` objects from the providers registered in *app*.

    Only providers that are *already registered* in the Application container
    are scanned — skills from un-registered providers are invisible.
    """

    def __init__(self, app: "Application") -> None:
        self._app = app
        self._skills: list[Skill] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> list[Skill]:
        """Return (and cache) the list of skills found across all providers."""
        if self._skills is not None:
            return self._skills

        self._skills = []
        for provider in self._app.providers:
            skills_dir = self._skills_dir_for(provider)
            if skills_dir is None or not skills_dir.is_dir():
                continue
            for skill_md in sorted(skills_dir.rglob("SKILL.md")):
                skill = self._load_skill(skill_md, provider.provider_key)
                if skill is not None:
                    self._skills.append(skill)

        return self._skills

    def get(self, name: str) -> Skill | None:
        """Return the :class:`Skill` with *name*, or *None* if not found."""
        return next((s for s in self.discover() if s.name == name), None)

    def reset(self) -> None:
        """Invalidate the discovery cache (useful in tests)."""
        self._skills = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _skills_dir_for(provider) -> Path | None:
        """Return the ``skills/`` directory that sits next to *provider*'s module.

        Returns *None* when the provider is defined in a non-file module (e.g.
        dynamically constructed in tests).
        """
        try:
            module = inspect.getmodule(provider)
            if module is None or not getattr(module, "__file__", None):
                return None
            provider_file = Path(module.__file__)
            return provider_file.parent / "skills"
        except (TypeError, OSError):
            return None

    @staticmethod
    def _load_skill(skill_md: Path, provider_key: str) -> Skill | None:
        """Parse *skill_md* and return a :class:`Skill`, or *None* on error."""
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            return None

        meta, body = _parse_frontmatter(text)

        name = meta.get("name", "").strip()
        description = meta.get("description", "").strip()

        if not name:
            # Use the parent directory name as a fallback
            name = skill_md.parent.name

        if not name:
            return None

        return Skill(
            name=name,
            description=description,
            path=skill_md,
            provider_key=provider_key,
            body=body.strip(),
        )
