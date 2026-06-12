"""GeminiRulesAdapter — splices rules into ``GEMINI.md`` via marker block."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi_startkit.skills.adapters.base import BaseAdapter
from fastapi_startkit.skills.rules.registry import Rule

_MARKER_START = "<!-- rules:start -->"
_MARKER_END = "<!-- rules:end -->"


class GeminiRulesAdapter(BaseAdapter):
    """Writes rules into the ``<!-- rules:start/end -->`` block of ``GEMINI.md``.

    Content outside the markers is never modified.
    """

    name = "gemini-rules"

    def render(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        gemini_md = self.base_path / "GEMINI.md"
        section = self._build_section(rules)
        changed = self._update_file(gemini_md, section)
        verb = "Synced" if changed else "Unchanged"
        return [f"[gemini] {verb} GEMINI.md rules section ({len(rules)} rule(s))"]

    def prune(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        """Re-render with the current (shorter) rule list."""
        return self.render(rules)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_section(rules: Sequence[Rule]) -> str:
        parts = [_MARKER_START]
        for rule in rules:
            parts.append(f"\n## {rule.name}\n")
            if rule.description:
                parts.append(f"{rule.description}\n")
            if rule.body:
                parts.append(f"\n{rule.body}\n")
        parts.append(_MARKER_END)
        return "\n".join(parts)

    def _update_file(self, path: Path, section: str) -> bool:
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        new_content = self._splice(original, section)
        if original == new_content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_content, encoding="utf-8")
        return True

    @staticmethod
    def _splice(original: str, section: str) -> str:
        start = original.find(_MARKER_START)
        end = original.find(_MARKER_END)
        if start != -1 and end != -1 and end > start:
            return original[:start] + section + original[end + len(_MARKER_END):]
        separator = "\n\n" if original and not original.endswith("\n\n") else ""
        return original + separator + section + "\n"
