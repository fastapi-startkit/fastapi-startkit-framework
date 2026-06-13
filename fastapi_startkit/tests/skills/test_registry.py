"""Tests for the provider-driven SkillRegistry.

A provider "declares" skills when its ``provider_key`` is a key in
:attr:`SkillRegistry.skills`. The framework ships a matching ``SKILL.md`` stub
for each declared destination; :meth:`SkillRegistry.discover` prefers a project
copy under ``.ai/`` and falls back to the bundled stub.
"""

from __future__ import annotations

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.masoniteorm import DatabaseProvider, Migrator, Model
from fastapi_startkit.fastapi.providers.fastapi_provider import FastAPIProvider
from fastapi_startkit.skills.registry import SkillRegistry, STUBS_BASE_PATH


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture(autouse=True)
def restore_db_manager():
    """DatabaseProvider.register() sets these class globals (absent by default).
    Snapshot and restore so registering it here can't leak into other tests."""
    _MISSING = object()
    saved = {cls: getattr(cls, "db_manager", _MISSING) for cls in (Model, Migrator)}
    yield
    for cls, value in saved.items():
        if value is _MISSING:
            if hasattr(cls, "db_manager"):
                delattr(cls, "db_manager")
        else:
            cls.db_manager = value


@pytest.fixture
def app(tmp_path):
    """App with the real fastapi + database skill-declaring providers."""
    return Application(
        base_path=tmp_path,
        env="testing",
        providers=[FastAPIProvider, DatabaseProvider],
    )


@pytest.fixture
def empty_app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# get_providers
# ---------------------------------------------------------------------------


def test_get_providers_returns_declaring_keys(app):
    keys = set(SkillRegistry(app).get_providers())
    assert keys == {"fastapi", "database"}


def test_get_providers_empty_when_none_declare(empty_app):
    assert list(SkillRegistry(empty_app).get_providers()) == []


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


def test_discover_loads_skills_from_bundled_stubs(app):
    skills = SkillRegistry(app).discover()
    # Names come from each stub's front-matter.
    assert {s.name for s in skills} == {"fastapi-startkit", "database"}
    assert {s.provider_key for s in skills} == {"fastapi", "database"}


def test_discover_empty_when_no_declaring_providers(empty_app):
    assert SkillRegistry(empty_app).discover() == []


def test_discover_prefers_project_copy_over_stub(app, tmp_path):
    # A user-edited project copy shadows the bundled stub.
    dest = tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("---\nname: my-fastapi\ndescription: edited\n---\nbody\n")

    skills = SkillRegistry(app).discover()
    names = {s.name for s in skills}
    assert "my-fastapi" in names
    assert "fastapi-startkit" not in names

    edited = next(s for s in skills if s.name == "my-fastapi")
    assert edited.path == dest


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


def test_publish_writes_stubs_and_renders_claude(app, tmp_path):
    messages = SkillRegistry(app).publish(target="claude")
    assert (tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "skills" / "fastapi-startkit" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()
    assert any("Syncing" in m for m in messages)


def test_publish_no_skills_returns_message(empty_app):
    messages = SkillRegistry(empty_app).publish(target="claude")
    assert any("No skills found" in m for m in messages)


def test_publish_unknown_target_returns_message(app):
    messages = SkillRegistry(app).publish(target="codex")
    assert any("Unknown target" in m for m in messages)


def test_publish_all_writes_both(app, tmp_path):
    SkillRegistry(app).publish(target="all")
    assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()
    assert (tmp_path / "GEMINI.md").exists()


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def test_base_path_property(app, tmp_path):
    assert SkillRegistry(app).base_path == tmp_path


def test_stubs_root_contains_bundled_stubs(app):
    root = SkillRegistry(app).stubs_root
    assert (root / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md").exists()
    assert STUBS_BASE_PATH.is_dir()
