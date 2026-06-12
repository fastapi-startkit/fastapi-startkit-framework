"""ClaudeRulesAdapter — deploys rules nested inside their parent skill directory.

Output layout mirrors the source convention::

    .claude/skills/<skill-name>/rules/<rule-name>.md

This means rules are co-located with the skill they document, so removing a
skill via ``ClaudeAdapter.prune()`` automatically removes its rules too
(``shutil.rmtree`` takes the whole skill directory).

NOTE: The exact output path convention is pending final confirmation from the
PR reviewer (agent 361).  The current implementation uses option (a):
``.claude/skills/<skill>/rules/<rule>.md`` — mirrors source nesting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi_startkit.skills.adapters.base import BaseAdapter
from fastapi_startkit.skills.rules.registry import Rule


class ClaudeRulesAdapter(BaseAdapter):
    """Writes each rule to ``.claude/skills/<skill-name>/rules/<rule-name>.md``.

    Writes are idempotent — the file is only (re)written when content changes.
    ``prune()`` removes stale rule files from skills that still exist; rules
    belonging to *removed* skills are cleaned up automatically when
    ``ClaudeAdapter.prune()`` removes the parent skill directory.
    """

    name = "claude-rules"

    def render(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        messages: list[str] = []
        for rule in rules:
            dest = self._rule_path(rule.skill_name, rule.name)
            written = self._write_idempotent(dest, rule.body)
            verb = "Synced" if written else "Unchanged"
            messages.append(
                f"[claude] {verb} .claude/skills/{rule.skill_name}/rules/{rule.name}.md"
            )
        return messages

    def prune(self, rules: Sequence[Rule]) -> list[str]:  # type: ignore[override]
        """Remove stale rule files from skills that still exist in *rules*.

        Rules whose entire parent skill directory has been removed by
        ``ClaudeAdapter.prune()`` are already gone — this method only needs
        to handle individual rule files that were removed from a still-present
        skill.
        """
        messages: list[str] = []
        # Build a set of (skill_name, rule_name) that should exist
        live = {(r.skill_name, r.name) for r in rules}

        skills_root = self.base_path / ".claude" / "skills"
        if not skills_root.is_dir():
            return messages

        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            rules_dir = skill_dir / "rules"
            if not rules_dir.is_dir():
                continue
            for rule_file in sorted(rules_dir.glob("*.md")):
                key = (skill_dir.name, rule_file.stem)
                if key not in live:
                    rule_file.unlink()
                    messages.append(
                        f"[claude] Pruned .claude/skills/{skill_dir.name}/rules/{rule_file.name}"
                    )
            # Remove empty rules/ dir
            if rules_dir.is_dir() and not any(rules_dir.iterdir()):
                rules_dir.rmdir()

        return messages

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rule_path(self, skill_name: str, rule_name: str) -> Path:
        return self.base_path / ".claude" / "skills" / skill_name / "rules" / f"{rule_name}.md"

    @staticmethod
    def _write_idempotent(path: Path, content: str) -> bool:
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True
