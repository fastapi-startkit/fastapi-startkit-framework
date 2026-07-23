"""SkillRegistry — maps providers to their skill files and publishes them.

Each provider key in :attr:`SkillRegistry.skills` points at one or more
``SKILL.md`` destinations under ``.ai/fastapi-startkit/``. The framework ships a
matching stub for each at ``skills/stubs/<dest>``.

* ``get_providers()`` — registered providers that declare skills (used by list).
* ``publish()``        — copy stubs into the project then render to AI agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING

from fastapi_startkit.skills.parser import Skill, SkillParser
from fastapi_startkit.support.collection import collect

if TYPE_CHECKING:
    from fastapi_startkit.application import Application
    from fastapi_startkit.support.collection import Collection

__all__ = ["Skill", "SkillRegistry", "STUBS_BASE_PATH"]

#: Source location of framework-shipped skill stubs, organised by provider key:
#:     stubs/.ai/fastapi-startkit/<provider_key>/SKILL.md
STUBS_BASE_PATH = Path(__file__).resolve().parent / "stubs" / ".ai" / "fastapi-startkit"


class SkillRegistry:
    skills = {
        "fastapi": [
            ".ai/fastapi-startkit/fastapi/SKILL.md",
        ],
        "database": [
            ".ai/fastapi-startkit/database/SKILL.md",
        ],
        "inertia": [
            ".ai/fastapi-startkit/inertia/SKILL.md",
        ],
    }

    def __init__(self, app: "Application") -> None:
        self.application = app
        self.parser = SkillParser()

    @property
    def base_path(self) -> Path:
        return Path(self.application.base_path)

    @property
    def stubs_root(self) -> Path:
        return STUBS_BASE_PATH.parent.parent  # .../skills/stubs

    def get_providers(self) -> "Collection":
        """Registered providers that declare skills (keyed by provider key)."""
        return (
            collect(self.application.providers)
            .map(lambda provider: provider.provider_key)
            .filter(lambda key: key in self.skills)
        )

    def discover(self) -> list[Skill]:
        """Load a Skill for every declared file of every registered provider.

        Prefers the project copy under ``.ai/`` (so user edits flow through) and
        falls back to the bundled stub when the project hasn't published it yet.
        """
        skills: list[Skill] = []
        for provider_key in self.get_providers():
            for dest in self.skills.get(provider_key, []):
                source = self.base_path / dest
                if not source.is_file():
                    source = self.stubs_root / dest
                skill = self.parser.parse(source, provider_key)
                if skill is not None:
                    skills.append(skill)

        return skills

    def publish(
        self,
        target: str = "all",
        prune: bool = False,
        force: bool = False,
        confirm: Callable[..., bool] | None = None,
    ) -> list[str]:
        """Copy stubs into the project, then render skills to the AI agent(s).

        Existing destination files are preserved unless *force* is set or
        *confirm* approves the overwrite — matching ``provider:publish``.

        Returns human-readable log lines for the calling command to print.
        """
        messages = self._publish_stubs(force=force, confirm=confirm)

        skills = self.discover()
        if not skills:
            messages.append("<comment>No skills found in any registered provider.</comment>")
            return messages

        adapters = self._resolve_adapters(target)
        if not adapters:
            messages.append(f"<error>Unknown target '{target}'. Use: claude, gemini, all.</error>")
            return messages

        messages.append(f"<info>Syncing {len(skills)} skill(s) to: {target}…</info>")
        for adapter in adapters:
            messages.extend(adapter.render(skills, force=force, confirm=confirm))
            if prune:
                messages.extend(adapter.prune(skills))
        return messages

    def _publish_stubs(
        self,
        force: bool = False,
        confirm: Callable[..., bool] | None = None,
    ) -> list[str]:
        """Copy bundled stubs into the project's ``.ai/``.

        A missing file is always written. An existing file is left untouched
        (preserving user edits) unless *force* is set or *confirm* approves the
        overwrite — so framework stub updates can be pulled in deliberately.
        """
        import shutil

        messages: list[str] = []
        for provider_key in self.get_providers():
            for dest in self.skills.get(provider_key, []):
                source = self.stubs_root / dest
                if not source.is_file():
                    continue

                dest_path = self.base_path / dest
                existed = dest_path.exists()
                if existed and not force:
                    if confirm is None or not confirm(
                        f"  <comment>{dest}</comment> already exists. Overwrite?", default=False
                    ):
                        messages.append(f"Skipped <comment>{dest}</comment> (already exists)")
                        continue

                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest_path)
                verb = "Overwrote" if existed else "Published"
                messages.append(f"{verb} <info>{dest}</info>")
        return messages

    def _resolve_adapters(self, target: str) -> list:
        from fastapi_startkit.skills.adapters import ClaudeAdapter, GeminiAdapter

        all_adapters = {
            "claude": ClaudeAdapter,
            "gemini": GeminiAdapter,
        }

        if target == "all":
            return [cls(self.base_path) for cls in all_adapters.values()]

        cls = all_adapters.get(target)
        return [cls(self.base_path)] if cls else []
