"""SkillRegistry — reads canonical skills from ``.ai/deployments/core.html``.

All skills are defined in a single central HTML file at::

    <project-root>/.ai/deployments/core.html

Each skill is a ``<section>`` element with two required attributes:

.. code-block:: html

    <section data-skill="my-skill" data-description="One-line description.">
    Markdown body content goes here.
    </section>

The file is Jinja2-compatible — add ``{% %}`` / ``{{ }}`` expressions freely;
they are passed through as-is until a future Jinja2 render step is wired up.

Running ``artisan skills:sync`` deploys the skills in this file to every
configured AI agent target (Claude Code, Gemini CLI, …).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi_startkit.application import Application

#: Relative path of the central skill definition file inside the project root.
CORE_HTML_PATH = Path(".ai") / "deployments" / "core.html"


@dataclass
class Skill:
    """Canonical skill metadata parsed from ``.ai/deployments/core.html``."""

    name: str
    description: str
    path: Path          # always points to the core.html source file
    provider_key: str = ""

    # Markdown body — the text content of the <section> element
    body: str = field(default="", repr=False)


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------


class _CoreHtmlParser(HTMLParser):
    """Minimal SAX-style parser that extracts ``<section data-skill=…>`` blocks."""

    def __init__(self) -> None:
        super().__init__()
        self._in_section: bool = False
        self._current_name: str = ""
        self._current_desc: str = ""
        self._buf: list[str] = []
        self.skills: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag != "section":
            return
        attrs_dict = dict(attrs)
        name = (attrs_dict.get("data-skill") or "").strip()
        if not name:
            return
        self._in_section = True
        self._current_name = name
        self._current_desc = (attrs_dict.get("data-description") or "").strip()
        self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "section" and self._in_section:
            self.skills.append(
                {
                    "name": self._current_name,
                    "description": self._current_desc,
                    "body": "".join(self._buf).strip(),
                }
            )
            self._in_section = False
            self._current_name = ""
            self._current_desc = ""
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._in_section:
            self._buf.append(data)

    # Comments and other nodes inside a section are collected verbatim
    def handle_comment(self, data: str) -> None:
        if self._in_section:
            self._buf.append(f"<!--{data}-->")


def parse_core_html(path: Path) -> list[dict]:
    """Parse *path* and return a list of raw skill dicts (name, description, body)."""
    text = path.read_text(encoding="utf-8")
    parser = _CoreHtmlParser()
    parser.feed(text)
    return parser.skills


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class SkillRegistry:
    """Loads :class:`Skill` objects from ``.ai/deployments/core.html``.

    The registry reads the central HTML skill file located at::

        {base_path}/.ai/deployments/core.html

    If the file does not exist, :meth:`discover` returns an empty list and
    prints a helpful hint.

    Usage::

        from fastapi_startkit.application import app
        registry = app().make("skills.registry")
        skills = registry.discover()
    """

    def __init__(self, app: "Application") -> None:
        self._app = app
        self._skills: list[Skill] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def core_html_path(self) -> Path:
        """Absolute path to the central skill definition file."""
        return Path(self._app.base_path) / CORE_HTML_PATH

    def discover(self) -> list[Skill]:
        """Return (and cache) the list of skills parsed from ``core.html``."""
        if self._skills is not None:
            return self._skills

        source = self.core_html_path

        if not source.exists():
            self._skills = []
            return self._skills

        raw_skills = parse_core_html(source)
        self._skills = [
            Skill(
                name=raw["name"],
                description=raw["description"],
                path=source,
                provider_key="core",
                body=raw["body"],
            )
            for raw in raw_skills
            if raw.get("name")
        ]

        return self._skills

    def get(self, name: str) -> Skill | None:
        """Return the :class:`Skill` with *name*, or *None* if not found."""
        return next((s for s in self.discover() if s.name == name), None)

    def reset(self) -> None:
        """Invalidate the discovery cache (useful in tests)."""
        self._skills = None
