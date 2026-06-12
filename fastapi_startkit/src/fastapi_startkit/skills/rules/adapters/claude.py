"""ClaudeRulesAdapter — deploys rules to ``.claude/rules/<name>.md``."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi_startkit.skills.adapters.base import BaseAdapter
from fastapi_startkit.skills.rules.registry import Rule


class ClaudeRulesAdapter(BaseAdapter):
    """Writes each rule to ``.claude/rules/<rule-name>.md``.

    Writes are idempotent — the file is only (re)written when its content
    would change.  ``--prune`` removes rule files no longer in the registry.
    """

    name = "claude-rules"

    def render(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        messages: list[str] = []
        for rule in rules:
            dest = self._rule_path(rule.name)
            written = self._write_idempotent(dest, rule.body)
            verb = "Synced" if written else "Unchanged"
            messages.append(f"[claude] {verb} .claude/rules/{rule.name}.md")
        return messages

    def prune(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        """Remove ``.claude/rules/<name>.md`` files not in *rules*."""
        messages: list[str] = []
        known = {r.name for r in rules}
        rules_dir = self.base_path / ".claude" / "rules"
        if not rules_dir.is_dir():
            return messages

        for child in sorted(rules_dir.glob("*.md")):
            if child.stem not in known:
                child.unlink()
                messages.append(f"[claude] Pruned .claude/rules/{child.name}")
        return messages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rule_path(self, rule_name: str) -> Path:
        return self.base_path / ".claude" / "rules" / f"{rule_name}.md"

    @staticmethod
    def _write_idempotent(path: Path, content: str) -> bool:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
