"""GeminiAdapter — renders skills into ``GEMINI.md`` via marker blocks.

The adapter manages only the region of ``GEMINI.md`` that lies between the
``<!-- skills:start -->`` and ``<!-- skills:end -->`` markers.  Content
outside those markers is **never** modified, making the adapter safe to use
even when the user has hand-edited the rest of the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from fastapi_startkit.skills.registry import Skill
from .base import BaseAdapter

_MARKER_START = "<!-- skills:start -->"
_MARKER_END = "<!-- skills:end -->"


class GeminiAdapter(BaseAdapter):
    """Writes canonical skills into ``GEMINI.md`` with HTML comment markers.

    If ``GEMINI.md`` does not exist it is created from scratch.  If it exists
    the content between the markers is replaced; everything outside is left
    unchanged.  The write is idempotent.
    """

    name = "gemini"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        skills: Sequence[Skill],
        force: bool = False,
        confirm: Callable[..., bool] | None = None,
    ) -> list[str]:
        # GEMINI.md edits are confined to the skills marker block, so user
        # content is never clobbered — force/confirm are accepted for a uniform
        # adapter interface but the block is always kept in sync.
        gemini_md = self.base_path / "GEMINI.md"
        new_section = self._build_section(skills)
        changed = self._update_file(gemini_md, new_section)
        verb = "Updated" if changed else "Unchanged"
        return [f"[gemini] {verb} <info>GEMINI.md</info> ({len(skills)} skill(s))"]

    def prune(self, skills: Sequence[Skill]) -> list[str]:
        """For Gemini, pruning just re-renders with the current skill list.

        Since everything lives in a single file within a marked block,
        rendering the new (shorter) list is equivalent to pruning.
        """
        return self.render(skills)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_section(self, skills: Sequence[Skill]) -> str:
        """Return the full marker block to inject into GEMINI.md."""
        parts = [_MARKER_START]
        for skill in skills:
            parts.append(f"\n## {skill.name}\n")
            if skill.description:
                parts.append(f"{skill.description}\n")
            if skill.body:
                parts.append(f"\n{skill.body}\n")
        parts.append(_MARKER_END)
        return "\n".join(parts)

    def _update_file(self, path: Path, section: str) -> bool:
        """Inject *section* into *path*, preserving content outside markers.

        Returns *True* when the file was (re)written, *False* when unchanged.
        """
        if path.exists():
            original = path.read_text(encoding="utf-8")
        else:
            original = ""

        new_content = self._splice(original, section)

        if original == new_content:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        return True

    @staticmethod
    def _splice(original: str, section: str) -> str:
        """Replace the skills block inside *original* with *section*.

        If the markers do not exist yet the section is appended to the file
        (separated by a blank line).
        """
        start_idx = original.find(_MARKER_START)
        end_idx = original.find(_MARKER_END)

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            before = original[:start_idx]
            after = original[end_idx + len(_MARKER_END) :]
            return before + section + after
        else:
            # No markers yet — append
            separator = "\n\n" if original and not original.endswith("\n\n") else ""
            return original + separator + section + "\n"
