"""BaseAdapter — abstract base class for all skill adapters.

New adapters (e.g. Codex) only need to subclass :class:`BaseAdapter` and
implement :meth:`render` and :meth:`prune`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Sequence

from fastapi_startkit.skills.registry import Skill


class BaseAdapter(ABC):
    """Abstract base for skill adapters.

    Parameters
    ----------
    base_path:
        Root of the project (where ``.claude/``, ``GEMINI.md``, etc. live).
        Defaults to the current working directory.
    """

    #: Short identifier shown in CLI output (e.g. "claude", "gemini").
    name: str = ""

    def __init__(self, base_path: Path | str | None = None) -> None:
        self.base_path = Path(base_path) if base_path else Path.cwd()

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def render(
        self,
        skills: Sequence[Skill],
        force: bool = False,
        confirm: Callable[..., bool] | None = None,
    ) -> list[str]:
        """Write *skills* to the target format.

        Existing files are preserved unless *force* is true or *confirm*
        returns true for the overwrite prompt — mirroring ``provider:publish``.

        Returns a list of human-readable lines describing what was written
        (suitable for printing in the ``ai:skills`` command).
        """

    @abstractmethod
    def prune(self, skills: Sequence[Skill]) -> list[str]:
        """Remove previously-synced skills that are *not* in *skills*.

        Returns a list of human-readable lines describing what was removed.
        """
