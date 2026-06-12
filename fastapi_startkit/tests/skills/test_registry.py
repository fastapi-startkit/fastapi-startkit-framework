"""Tests for SkillRegistry (task #139)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.providers import Provider
from fastapi_startkit.skills.registry import Skill, SkillRegistry, _parse_frontmatter


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


# ---------------------------------------------------------------------------
# _parse_frontmatter unit tests
# ---------------------------------------------------------------------------


def test_parse_frontmatter_basic():
    text = textwrap.dedent("""\
        ---
        name: my-skill
        description: Does something useful
        ---
        Body content here.
    """)
    meta, body = _parse_frontmatter(text)
    assert meta["name"] == "my-skill"
    assert meta["description"] == "Does something useful"
    assert "Body content here." in body


def test_parse_frontmatter_missing_fence():
    text = "No YAML front-matter here."
    meta, body = _parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_unclosed_fence():
    text = "---\nname: oops\n"
    meta, body = _parse_frontmatter(text)
    assert meta == {}


# ---------------------------------------------------------------------------
# SkillRegistry — discovery tests
# ---------------------------------------------------------------------------


def _make_skill_md(directory: Path, name: str, description: str, body: str = "") -> Path:
    """Helper: write a SKILL.md into *directory/name/SKILL.md*."""
    skill_dir = directory / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    lines = ["---", f"name: {name}", f"description: {description}", "---"]
    if body:
        lines += ["", body]
    skill_file.write_text("\n".join(lines))
    return skill_file


class _DynamicProvider(Provider):
    """Provider whose skills/ directory is injected at runtime (for testing)."""

    _skills_path: Path | None = None
    provider_key = "dynamic"

    def register(self):
        pass

    def boot(self):
        pass


def test_registry_discovers_skills_from_registered_providers(tmp_path, monkeypatch, app):
    """SkillRegistry.discover() returns skills from providers with a skills/ dir."""
    # Create a fake provider module file and skills/ dir
    provider_dir = tmp_path / "mypkg"
    provider_dir.mkdir()
    fake_module_file = provider_dir / "provider.py"
    fake_module_file.write_text("# fake")

    skills_dir = provider_dir / "skills"
    _make_skill_md(skills_dir, "fastapi-routing", "Helps with FastAPI routing")
    _make_skill_md(skills_dir, "orm-queries", "Helps with ORM queries", body="Use `Model.where(...)` for filtering.")

    # Monkeypatch inspect.getmodule to return a fake module for the provider
    import inspect as _inspect
    import types

    fake_module = types.ModuleType("mypkg.provider")
    fake_module.__file__ = str(fake_module_file)

    original_getmodule = _inspect.getmodule

    def patched_getmodule(obj, _filename=None):
        if isinstance(obj, _DynamicProvider):
            return fake_module
        return original_getmodule(obj, _filename)

    monkeypatch.setattr(_inspect, "getmodule", patched_getmodule)

    registry = SkillRegistry(app)
    # Inject the provider instance directly
    app.providers.append(_DynamicProvider(app))

    skills = registry.discover()

    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"fastapi-routing", "orm-queries"}

    orm_skill = next(s for s in skills if s.name == "orm-queries")
    assert "Model.where" in orm_skill.body


def test_registry_ignores_providers_without_skills_dir(tmp_path, app):
    """SkillRegistry does not crash on providers that have no skills/ dir."""
    registry = SkillRegistry(app)
    skills = registry.discover()
    # Default providers (ConfigurationProvider, AppProvider) have no skills/
    assert isinstance(skills, list)


def test_registry_caches_results(tmp_path, monkeypatch, app):
    """Calling discover() twice returns the same list without re-scanning."""
    registry = SkillRegistry(app)
    first = registry.discover()
    second = registry.discover()
    assert first is second  # same object, not recomputed


def test_registry_reset_clears_cache(tmp_path, app):
    registry = SkillRegistry(app)
    registry.discover()
    assert registry._skills is not None
    registry.reset()
    assert registry._skills is None


def test_registry_get_by_name(tmp_path, monkeypatch, app):
    import inspect as _inspect
    import types

    provider_dir = tmp_path / "pkg"
    provider_dir.mkdir()
    fake_module = types.ModuleType("pkg.provider")
    fake_module.__file__ = str(provider_dir / "provider.py")

    skills_dir = provider_dir / "skills"
    _make_skill_md(skills_dir, "console-commands", "Artisan console commands")

    original_getmodule = _inspect.getmodule

    def patched(obj, _filename=None):
        if isinstance(obj, _DynamicProvider):
            return fake_module
        return original_getmodule(obj, _filename)

    monkeypatch.setattr(_inspect, "getmodule", patched)

    registry = SkillRegistry(app)
    app.providers.append(_DynamicProvider(app))

    skill = registry.get("console-commands")
    assert skill is not None
    assert skill.name == "console-commands"

    missing = registry.get("does-not-exist")
    assert missing is None
