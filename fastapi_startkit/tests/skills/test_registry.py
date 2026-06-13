"""Tests for the provider-driven SkillRegistry.

A provider "declares" skills when its ``provider_key`` is a key in
:attr:`SkillRegistry.skills`. The real ``FastAPIProvider`` declares the
``fastapi`` skill; ``AISkillProvider`` (key ``ai_skill``) does not, so it
exercises the registry's filtering. The framework ships a matching ``SKILL.md``
stub per declared destination, and :meth:`SkillRegistry.discover` prefers a
project copy under ``.ai/`` over the bundled stub.
"""

from __future__ import annotations

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi.providers.fastapi_provider import FastAPIProvider
from fastapi_startkit.skills import AISkillProvider
from fastapi_startkit.skills.registry import SkillRegistry, STUBS_BASE_PATH

#: Claude skill dir for the fastapi skill (from the stub's front-matter name).
FASTAPI_SKILL = "fastapi-startkit"


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    """App with a skill-declaring provider (fastapi) and a non-declaring one."""
    return Application(
        base_path=tmp_path,
        env="testing",
        providers=[AISkillProvider, FastAPIProvider],
    )


@pytest.fixture
def empty_app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


# ---------------------------------------------------------------------------
# get_providers
# ---------------------------------------------------------------------------


def test_get_providers_returns_only_declaring_keys(app):
    # AISkillProvider (ai_skill) is registered but not declared, so it's filtered.
    assert set(SkillRegistry(app).get_providers()) == {"fastapi"}


def test_get_providers_empty_when_none_declare(empty_app):
    assert list(SkillRegistry(empty_app).get_providers()) == []


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


def test_discover_loads_skill_from_bundled_stub(app):
    skills = SkillRegistry(app).discover()
    # Name comes from the stub's front-matter; provider_key from the declarer.
    assert {s.name for s in skills} == {FASTAPI_SKILL}
    assert {s.provider_key for s in skills} == {"fastapi"}


def test_discover_empty_when_no_declaring_providers(empty_app):
    assert SkillRegistry(empty_app).discover() == []


def test_discover_prefers_project_copy_over_stub(app, tmp_path):
    # A user-edited project copy shadows the bundled stub.
    dest = tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md"
    dest.parent.mkdir(parents=True)
    dest.write_text("---\nname: my-fastapi\ndescription: edited\n---\nbody\n")

    skills = SkillRegistry(app).discover()
    assert {s.name for s in skills} == {"my-fastapi"}
    assert skills[0].path == dest


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


def test_publish_writes_stub_and_renders_claude(app, tmp_path):
    messages = SkillRegistry(app).publish(target="claude")
    assert (tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md").exists()
    assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()
    assert any("Syncing" in m for m in messages)


def test_publish_no_skills_returns_message(empty_app):
    messages = SkillRegistry(empty_app).publish(target="claude")
    assert any("No skills found" in m for m in messages)


def test_publish_unknown_target_returns_message(app):
    messages = SkillRegistry(app).publish(target="codex")
    assert any("Unknown target" in m for m in messages)


def test_publish_all_writes_both(app, tmp_path):
    SkillRegistry(app).publish(target="all")
    assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()
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
