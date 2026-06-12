"""Tests for skills:sync and skills:list commands (task #141)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.skills.registry import Skill, SkillRegistry, CORE_HTML_PATH
from fastapi_startkit.skills.commands.sync import SkillsSyncCommand
from fastapi_startkit.skills.commands.list import SkillsListCommand


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


def _write_core_html(tmp_path: Path, skills: list[tuple[str, str]]) -> None:
    """Write a core.html with the given (name, description) skills."""
    core = tmp_path / CORE_HTML_PATH
    core.parent.mkdir(parents=True, exist_ok=True)
    sections = "\n".join(
        f'<section data-skill="{name}" data-description="{desc}">Skill body for {name}.</section>'
        for name, desc in skills
    )
    core.write_text(f"<!DOCTYPE html>\n{sections}\n", encoding="utf-8")


def _make_skill(name: str, desc: str = "A skill.", body: str = "") -> Skill:
    return Skill(name=name, description=desc, path=Path("/dev/null"), provider_key="core", body=body)


def _run_command(cmd_class, container, args: list[str] | None = None):
    """Execute a command's handle() with lightweight fake IO."""
    cmd = cmd_class()
    cmd.set_container(container)

    option_values: dict = {}
    if args:
        for arg in args:
            if arg.startswith("--"):
                k = arg.lstrip("-").split("=")[0]
                v = arg.split("=")[1] if "=" in arg else True
                option_values[k] = v

    output_lines: list[str] = []
    cmd.option = lambda k, default=None: option_values.get(k, default)
    cmd.line = lambda msg, *a, **kw: output_lines.append(msg)
    cmd.info = lambda msg, *a, **kw: output_lines.append(msg)

    return_code = cmd.handle()
    return return_code, output_lines


# ===========================================================================
# SkillsSyncCommand
# ===========================================================================


class TestSkillsSyncCommand:
    def test_sync_all_writes_claude_and_gemini(self, tmp_path, app):
        _write_core_html(tmp_path, [("orm-routing", "ORM routing skill")])

        registry = SkillRegistry(app)
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=all"])

        assert return_code == 0
        assert (tmp_path / ".claude" / "skills" / "orm-routing" / "SKILL.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_claude_only(self, tmp_path, app):
        _write_core_html(tmp_path, [("console-commands", "Artisan commands")])
        app.bind("skills.registry", SkillRegistry(app))

        return_code, _ = _run_command(SkillsSyncCommand, app, args=["--target=claude"])

        assert return_code == 0
        assert (tmp_path / ".claude" / "skills" / "console-commands" / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_gemini_only(self, tmp_path, app):
        _write_core_html(tmp_path, [("fastapi-routing", "FastAPI routing")])
        app.bind("skills.registry", SkillRegistry(app))

        return_code, _ = _run_command(SkillsSyncCommand, app, args=["--target=gemini"])

        assert return_code == 0
        assert not (tmp_path / ".claude").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_unknown_target_returns_error(self, tmp_path, app):
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=codex"])

        assert return_code == 1
        assert any("Unknown target" in ln for ln in lines)

    def test_sync_no_core_html_exits_gracefully(self, tmp_path, app):
        # No core.html file → registry returns empty list
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsSyncCommand, app)

        assert return_code == 0
        assert any("No skills" in ln for ln in lines)

    def test_sync_prune_flag_removes_old_claude_skills(self, tmp_path, app):
        # Pre-create an orphan skill dir
        old_dir = tmp_path / ".claude" / "skills" / "old-skill"
        old_dir.mkdir(parents=True)
        (old_dir / "SKILL.md").write_text("---\nname: old-skill\n---\n")

        _write_core_html(tmp_path, [("new-skill", "New skill")])
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=claude", "--prune"])

        assert return_code == 0
        assert not old_dir.exists()
        assert any("Pruned" in ln for ln in lines)

    def test_sync_claude_skill_content_includes_body(self, tmp_path, app):
        core = tmp_path / CORE_HTML_PATH
        core.parent.mkdir(parents=True, exist_ok=True)
        core.write_text(
            '<section data-skill="orm" data-description="ORM helpers.">'
            "Use `Model.where(...)` for filtering."
            "</section>",
            encoding="utf-8",
        )
        app.bind("skills.registry", SkillRegistry(app))

        _run_command(SkillsSyncCommand, app, args=["--target=claude"])

        content = (tmp_path / ".claude" / "skills" / "orm" / "SKILL.md").read_text()
        assert "Model.where" in content

    def test_command_name_and_description(self):
        cmd = SkillsSyncCommand()
        assert cmd.name == "skills:sync"
        assert "sync" in cmd.description.lower()


# ===========================================================================
# SkillsListCommand
# ===========================================================================


class TestSkillsListCommand:
    def test_list_shows_skills_from_core_html(self, tmp_path, app):
        _write_core_html(
            tmp_path,
            [("fastapi-routing", "FastAPI routing helpers"), ("orm-queries", "ORM query helpers")],
        )
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsListCommand, app)

        assert return_code == 0
        all_output = "\n".join(lines)
        assert "fastapi-routing" in all_output
        assert "orm-queries" in all_output

    def test_list_shows_pending_when_not_synced(self, tmp_path, app):
        _write_core_html(tmp_path, [("my-skill", "My skill")])
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsListCommand, app)
        all_output = "\n".join(lines)

        assert "pending" in all_output

    def test_list_shows_synced_when_claude_file_exists(self, tmp_path, app):
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n")

        _write_core_html(tmp_path, [("my-skill", "My skill")])
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsListCommand, app)
        all_output = "\n".join(lines)

        assert "synced" in all_output

    def test_list_no_core_html_shows_message(self, tmp_path, app):
        app.bind("skills.registry", SkillRegistry(app))

        return_code, lines = _run_command(SkillsListCommand, app)

        assert return_code == 0
        assert any("No skills" in ln for ln in lines)

    def test_command_name_and_description(self):
        cmd = SkillsListCommand()
        assert cmd.name == "skills:list"
