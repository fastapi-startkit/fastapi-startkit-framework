"""Tests for skills:sync and skills:list commands (task #141)."""

from __future__ import annotations

import textwrap
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.providers import Provider
from fastapi_startkit.skills.registry import Skill, SkillRegistry
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


def _make_skill(name: str, desc: str = "A skill.", body: str = "") -> Skill:
    return Skill(name=name, description=desc, path=Path("/dev/null"), provider_key="test", body=body)


def _run_command(cmd_class, container, args: list[str] | None = None):
    """Run a Cleo command directly using its handle() method.

    We fake the IO and option parsing to keep tests free of Cleo internals.
    """
    from cleo.io.null_io import NullIO
    from cleo.io.inputs.string_input import StringInput
    from cleo.io.outputs.output import Output

    cmd = cmd_class()
    cmd.set_container(container)

    # Build a simple mock for option() and line()
    option_values = {}
    if args:
        for i, arg in enumerate(args):
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
        skills = [_make_skill("orm-routing", "ORM routing skill")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=all"])

        assert return_code == 0
        # Claude adapter should have written the file
        assert (tmp_path / ".claude" / "skills" / "orm-routing" / "SKILL.md").exists()
        # Gemini adapter should have written GEMINI.md
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_claude_only(self, tmp_path, app):
        skills = [_make_skill("console-commands")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, _ = _run_command(SkillsSyncCommand, app, args=["--target=claude"])

        assert return_code == 0
        assert (tmp_path / ".claude" / "skills" / "console-commands" / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_gemini_only(self, tmp_path, app):
        skills = [_make_skill("fastapi-routing")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, _ = _run_command(SkillsSyncCommand, app, args=["--target=gemini"])

        assert return_code == 0
        assert not (tmp_path / ".claude").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_unknown_target_returns_error(self, tmp_path, app):
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = []
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=codex"])

        assert return_code == 1
        assert any("Unknown target" in ln for ln in lines)

    def test_sync_no_skills_exits_gracefully(self, tmp_path, app):
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = []
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsSyncCommand, app)

        assert return_code == 0
        assert any("No skills" in ln for ln in lines)

    def test_sync_prune_flag_removes_old_skills(self, tmp_path, app):
        # Pre-create a skill that is not in the registry
        old_skill_dir = tmp_path / ".claude" / "skills" / "old-skill"
        old_skill_dir.mkdir(parents=True)
        (old_skill_dir / "SKILL.md").write_text("---\nname: old-skill\ndescription: gone\n---\n")

        skills = [_make_skill("new-skill")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsSyncCommand, app, args=["--target=claude", "--prune"])

        assert return_code == 0
        assert not old_skill_dir.exists()
        assert any("Pruned" in ln for ln in lines)

    def test_command_name_and_description(self):
        cmd = SkillsSyncCommand()
        assert cmd.name == "skills:sync"
        assert "sync" in cmd.description.lower()


# ===========================================================================
# SkillsListCommand
# ===========================================================================


class TestSkillsListCommand:
    def test_list_shows_skills(self, tmp_path, app):
        skills = [
            _make_skill("fastapi-routing", "FastAPI routing helpers"),
            _make_skill("orm-queries", "ORM query helpers"),
        ]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsListCommand, app)

        assert return_code == 0
        all_output = "\n".join(lines)
        assert "fastapi-routing" in all_output
        assert "orm-queries" in all_output

    def test_list_shows_pending_when_not_synced(self, tmp_path, app):
        skills = [_make_skill("my-skill")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsListCommand, app)
        all_output = "\n".join(lines)

        assert "pending" in all_output

    def test_list_shows_synced_when_claude_file_exists(self, tmp_path, app):
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n")

        skills = [_make_skill("my-skill")]
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = skills
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsListCommand, app)
        all_output = "\n".join(lines)

        assert "synced" in all_output

    def test_list_no_skills_message(self, tmp_path, app):
        registry = MagicMock(spec=SkillRegistry)
        registry.discover.return_value = []
        app.bind("skills.registry", registry)

        return_code, lines = _run_command(SkillsListCommand, app)

        assert return_code == 0
        assert any("No skills" in ln for ln in lines)

    def test_command_name_and_description(self):
        cmd = SkillsListCommand()
        assert cmd.name == "skills:list"
        assert "list" in cmd.description.lower() or "skill" in cmd.description.lower()
