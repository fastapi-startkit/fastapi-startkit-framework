"""Tests for SkillRegistry reading from .ai/deployments/core.html (task #139)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.skills.registry import (
    Skill,
    SkillRegistry,
    _CoreHtmlParser,
    parse_core_html,
    CORE_HTML_PATH,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


def _write_core_html(tmp_path: Path, content: str) -> Path:
    """Write *content* to the canonical core.html location under *tmp_path*."""
    core = tmp_path / CORE_HTML_PATH
    core.parent.mkdir(parents=True, exist_ok=True)
    core.write_text(content, encoding="utf-8")
    return core


# ---------------------------------------------------------------------------
# _CoreHtmlParser unit tests
# ---------------------------------------------------------------------------


def test_parser_extracts_single_section():
    html = textwrap.dedent("""\
        <section data-skill="fastapi-routing" data-description="FastAPI routing helpers.">
        Use router.get() to register routes.
        </section>
    """)
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert len(parser.skills) == 1
    s = parser.skills[0]
    assert s["name"] == "fastapi-routing"
    assert s["description"] == "FastAPI routing helpers."
    assert "router.get()" in s["body"]


def test_parser_extracts_multiple_sections():
    html = textwrap.dedent("""\
        <section data-skill="skill-a" data-description="Skill A.">Body A.</section>
        <section data-skill="skill-b" data-description="Skill B.">Body B.</section>
    """)
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert len(parser.skills) == 2
    assert parser.skills[0]["name"] == "skill-a"
    assert parser.skills[1]["name"] == "skill-b"


def test_parser_skips_sections_without_data_skill():
    html = '<section data-description="No name here.">body</section>'
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert parser.skills == []


def test_parser_ignores_non_section_tags():
    html = textwrap.dedent("""\
        <div>some wrapper</div>
        <section data-skill="valid" data-description="desc.">content</section>
        <p>irrelevant</p>
    """)
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert len(parser.skills) == 1
    assert parser.skills[0]["name"] == "valid"


def test_parser_handles_html_comments_inside_section():
    html = textwrap.dedent("""\
        <section data-skill="annotated" data-description="With comments.">
        <!-- Jinja2: {{ var }} -->
        Some body text.
        </section>
    """)
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert len(parser.skills) == 1
    body = parser.skills[0]["body"]
    assert "Some body text." in body


def test_parser_trims_body_whitespace():
    html = '<section data-skill="s" data-description="d.">\n\n  trimmed  \n\n</section>'
    parser = _CoreHtmlParser()
    parser.feed(html)
    assert parser.skills[0]["body"] == "trimmed"


# ---------------------------------------------------------------------------
# parse_core_html
# ---------------------------------------------------------------------------


def test_parse_core_html_returns_skill_dicts(tmp_path):
    core = _write_core_html(tmp_path, textwrap.dedent("""\
        <section data-skill="orm-queries" data-description="ORM query helpers.">
        Use Model.where().get() for filtering.
        </section>
    """))
    skills = parse_core_html(core)
    assert len(skills) == 1
    assert skills[0]["name"] == "orm-queries"


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


def test_registry_discovers_skills_from_core_html(tmp_path, app):
    _write_core_html(tmp_path, textwrap.dedent("""\
        <section data-skill="fastapi-routing" data-description="FastAPI routing.">
        Router body.
        </section>
        <section data-skill="orm-queries" data-description="ORM queries.">
        ORM body.
        </section>
    """))

    registry = SkillRegistry(app)
    skills = registry.discover()

    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"fastapi-routing", "orm-queries"}


def test_registry_returns_empty_list_when_core_html_missing(tmp_path, app):
    registry = SkillRegistry(app)
    skills = registry.discover()
    assert skills == []


def test_registry_skill_path_points_to_core_html(tmp_path, app):
    _write_core_html(tmp_path, '<section data-skill="s" data-description="d.">body</section>')
    registry = SkillRegistry(app)
    skills = registry.discover()
    assert skills[0].path == tmp_path / CORE_HTML_PATH


def test_registry_skill_body_is_captured(tmp_path, app):
    _write_core_html(tmp_path, textwrap.dedent("""\
        <section data-skill="orm" data-description="ORM.">
        Use `Model.where(...)`
        </section>
    """))
    registry = SkillRegistry(app)
    skill = registry.get("orm")
    assert skill is not None
    assert "Model.where" in skill.body


def test_registry_caches_results(tmp_path, app):
    _write_core_html(tmp_path, '<section data-skill="s" data-description="d.">body</section>')
    registry = SkillRegistry(app)
    first = registry.discover()
    second = registry.discover()
    assert first is second


def test_registry_reset_clears_cache(tmp_path, app):
    _write_core_html(tmp_path, '<section data-skill="s" data-description="d.">body</section>')
    registry = SkillRegistry(app)
    registry.discover()
    assert registry._skills is not None
    registry.reset()
    assert registry._skills is None


def test_registry_get_returns_none_for_unknown(tmp_path, app):
    _write_core_html(tmp_path, '<section data-skill="s" data-description="d.">body</section>')
    registry = SkillRegistry(app)
    assert registry.get("does-not-exist") is None


def test_registry_get_returns_skill_by_name(tmp_path, app):
    _write_core_html(tmp_path, textwrap.dedent("""\
        <section data-skill="console-commands" data-description="Artisan console.">
        Extend Command class.
        </section>
    """))
    registry = SkillRegistry(app)
    skill = registry.get("console-commands")
    assert skill is not None
    assert skill.name == "console-commands"
    assert skill.provider_key == "core"


def test_registry_core_html_path_property(tmp_path, app):
    registry = SkillRegistry(app)
    assert registry.core_html_path == tmp_path / ".ai" / "deployments" / "core.html"
