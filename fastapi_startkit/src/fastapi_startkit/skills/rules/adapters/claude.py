"""ClaudeRulesAdapter — deploys rules to ``.claude/rules/<skill>/<rule>.md``.

Claude Code reads rules **only** from ``.claude/rules/``.  Rules written
anywhere else (e.g. ``.claude/skills/<skill>/rules/``) are silently ignored.

Output layout::

    .claude/rules/
        fastapi-best-practices/
            http-client.md
            validation.md
        orm-best-practices/
            queries.md

``prune()`` scans ``.claude/rules/`` independently of the skills adapter —
it removes individual rule files (and empty skill sub-dirs) that are no
longer present in the registry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi_startkit.skills.adapters.base import BaseAdapter
from fastapi_startkit.skills.rules.registry import Rule


class ClaudeRulesAdapter(BaseAdapter):
    """Writes each rule to ``.claude/rules/<skill-name>/<rule-name>.md``.

    Writes are idempotent — the file is only (re)written when content changes.
    ``prune()`` scans ``.claude/rules/`` and removes stale rule files and
    empty skill sub-directories.  It operates independently of
    ``ClaudeAdapter.prune()``.
    """

    name = "claude-rules"

    def render(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        messages: list[str] = []
        for rule in rules:
            dest = self._rule_path(rule.skill_name, rule.name)
            written = self._write_idempotent(dest, rule.body)
            verb = "Synced" if written else "Unchanged"
            messages.append(
                f"[claude] {verb} .claude/rules/{rule.skill_name}/{rule.name}.md"
            )
        return messages

    def prune(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        """Remove stale rule files from ``.claude/rules/``.

        Iterates every ``<skill-dir>/<rule>.md`` under ``.claude/rules/`` and
        removes any file whose ``(skill_name, rule_name)`` pair is absent from
        *rules*.  Empty skill sub-directories are removed afterwards.
        """
        messages: list[str] = []
        live = {(r.skill_name, r.name) for r in rules}

        rules_root = self.base_path / ".claude" / "rules"
        if not rules_root.is_dir():
            return messages

        for skill_dir in sorted(rules_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            for rule_file in sorted(skill_dir.glob("*.md")):
                key = (skill_dir.name, rule_file.stem)
                if key not in live:
                    rule_file.unlink()
                    messages.append(
                        f"[claude] Pruned .claude/rules/{skill_dir.name}/{rule_file.name}"
                    )
            # Remove empty skill sub-directory
            if skill_dir.is_dir() and not any(skill_dir.iterdir()):
                skill_dir.rmdir()

        return messages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rule_path(self, skill_name: str, rule_name: str) -> Path:
        return self.base_path / ".claude" / "rules" / skill_name / f"{rule_name}.md"

    @staticmethod
    def _write_idempotent(path: Path, content: str) -> bool:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
