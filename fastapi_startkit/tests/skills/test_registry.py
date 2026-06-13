"""Tests for SkillRegistry reading from .ai/fastapi-startkit/skill/*/SKILL.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.skills.registry import (
    SkillRegistry,
    SKILLS_BASE_PATH,
    _parse_frontmatter,
)


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


def _write_skill(tmp_path: Path, name: str, description: str, body: str = "") -> Path:
    skill_dir = tmp_path / SKILLS_BASE_PATH / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    lines = ["---", f"name: {name}", f"description: {description}", "---"]
    if body:
        lines += ["", body]
    skill_md.write_text("\n".join(lines), encoding="utf-8")
    return skill_md


# -- _parse_frontmatter --

def test_parse_frontmatter_basic():
    text = "---\nname: fastapi-best-practices\ndescription: Apply for FastAPI code.\n---\nBody content here.\n"
    meta, body = _parse_frontmatter(text)
    assert meta["name"] == "fastapi-best-practices"
    assert meta["description"] == "Apply for FastAPI code."
    assert "Body content here." in body


def test_parse_frontmatter_missing_fence():
    text = "No front-matter here."
    meta, body = _parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_unclosed_fence():
    meta, body = _parse_frontmatter("---\nname: oops\n")
    assert meta == {}


# -- SkillRegistry --

def test_registry_discovers_skills_from_skill_dirs(tmp_path, app):
    _write_skill(tmp_path, "fastapi-routing", "FastAPI routing helpers", "Use Router.")
    _write_skill(tmp_path, "orm-queries", "ORM query helpers", "Use Model.where().")

    skills = SkillRegistry(app).discover()
    assert len(skills) == 2
    assert {s.name for s in skills} == {"fastapi-routing", "orm-queries"}


def test_registry_returns_empty_when_skills_dir_missing(tmp_path, app):
    assert SkillRegistry(app).discover() == []


def test_registry_skill_path_points_to_skill_md(tmp_path, app):
    path = _write_skill(tmp_path, "my-skill", "desc")
    skills = SkillRegistry(app).discover()
    assert skills[0].path == path


def test_registry_skill_body_captured(tmp_path, app):
    _write_skill(tmp_path, "orm", "ORM.", body="Use `Model.where(...)`")
    skill = SkillRegistry(app).get("orm")
    assert skill is not None
    assert "Model.where" in skill.body


def test_registry_uses_dir_name_fallback(tmp_path, app):
    skill_dir = tmp_path / SKILLS_BASE_PATH / "fallback-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("No front-matter.", encoding="utf-8")
    skills = SkillRegistry(app).discover()
    assert skills[0].name == "fallback-skill"


def test_registry_caches_results(tmp_path, app):
    _write_skill(tmp_path, "s", "d")
    r = SkillRegistry(app)
    assert r.discover() is r.discover()


def test_registry_reset_clears_cache(tmp_path, app):
    _write_skill(tmp_path, "s", "d")
    r = SkillRegistry(app)
    r.discover()
    r.reset()
    assert r._skills is None


def test_registry_get_returns_none_for_unknown(tmp_path, app):
    _write_skill(tmp_path, "s", "d")
    assert SkillRegistry(app).get("does-not-exist") is None


def test_registry_get_returns_skill_by_name(tmp_path, app):
    _write_skill(tmp_path, "console-commands", "Artisan console.")
    skill = SkillRegistry(app).get("console-commands")
    assert skill is not None
    assert skill.name == "console-commands"
    assert skill.provider_key == "fastapi-startkit"


def test_registry_skills_base_path_property(tmp_path, app):
    r = SkillRegistry(app)
    assert r.skills_base_path == tmp_path / ".ai" / "fastapi-startkit" / "skill"
