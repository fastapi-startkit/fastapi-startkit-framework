"""Tests for the ai:skills command (list + sync).

The skills module is provider-driven: a provider declares skills by having a
``provider_key`` that appears in :attr:`SkillRegistry.skills`. The framework's
real ``FastAPIProvider`` (``fastapi``) and ``DatabaseProvider`` (``database``)
declare the bundled skills, so the tests register the actual providers rather
than stubs. ``AISkillProvider`` binds the registry the command resolves.
"""

from __future__ import annotations

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.masoniteorm import DatabaseProvider, Migrator, Model
from fastapi_startkit.fastapi.providers.fastapi_provider import FastAPIProvider
from fastapi_startkit.skills import AISkillProvider
from fastapi_startkit.skills.commands import SkillsCommand


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
    """App with the real skill-declaring providers and a bound registry."""
    return Application(
        base_path=tmp_path,
        env="testing",
        providers=[AISkillProvider, FastAPIProvider, DatabaseProvider],
    )


@pytest.fixture
def empty_app(tmp_path):
    """App with no skill-declaring providers (registry still bound)."""
    return Application(base_path=tmp_path, env="testing", providers=[AISkillProvider])


def _run(cmd_class, container, args=None, choice="all"):
    """Instantiate a command, stub its Cleo I/O, and run handle().

    Returns ``(exit_code, lines)`` where ``lines`` is everything written via
    ``line``/``info``.
    """
    cmd = cmd_class()
    cmd.set_container(container)

    opts = {}
    for arg in args or []:
        if arg.startswith("--"):
            k = arg.lstrip("-").split("=")[0]
            v = arg.split("=")[1] if "=" in arg else True
            opts[k] = v

    lines = []
    cmd.option = lambda k, default=None: opts.get(k, default)
    cmd.line = lambda msg, *a, **kw: lines.append(msg)
    cmd.info = lambda msg, *a, **kw: lines.append(msg)
    cmd.choice = lambda *a, **kw: choice
    cmd.confirm = lambda *a, **kw: False
    return cmd.handle(), lines


# ===========================================================================
# ai:skills --list
# ===========================================================================


class TestSkillsListCommand:
    def test_list_shows_declaring_providers(self, app):
        code, lines = _run(SkillsCommand, app, ["--list"])
        assert code == 0
        out = "\n".join(lines)
        assert "fastapi" in out
        assert "database" in out

    def test_list_is_default_when_no_flags(self, app):
        code, lines = _run(SkillsCommand, app)
        assert code == 0
        out = "\n".join(lines)
        assert "fastapi" in out
        assert "database" in out

    def test_list_no_skills_shows_message(self, empty_app):
        code, lines = _run(SkillsCommand, empty_app, ["--list"])
        assert code == 0
        assert any("No skills" in l for l in lines)

    def test_command_name(self):
        assert SkillsCommand().name == "ai:skills"


# ===========================================================================
# ai:skills --sync
# ===========================================================================


class TestSkillsSyncCommand:
    def test_sync_claude_publishes_stubs_and_skill_files(self, app, tmp_path):
        code, _ = _run(SkillsCommand, app, ["--sync", "--target=claude"])
        assert code == 0
        # Stubs are copied into the project's .ai/ tree.
        assert (tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md").exists()
        assert (tmp_path / ".ai" / "fastapi-startkit" / "database" / "SKILL.md").exists()
        # ClaudeAdapter writes one dir per skill name (from stub front-matter).
        assert (tmp_path / ".claude" / "skills" / "fastapi-startkit" / "SKILL.md").exists()
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_gemini_only(self, app, tmp_path):
        code, _ = _run(SkillsCommand, app, ["--sync", "--target=gemini"])
        assert code == 0
        assert (tmp_path / "GEMINI.md").exists()
        assert not (tmp_path / ".claude").exists()

    def test_sync_all_writes_both(self, app, tmp_path):
        code, _ = _run(SkillsCommand, app, ["--sync", "--target=all"])
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_prune_implies_sync(self, app, tmp_path):
        # --prune alone (no --sync) still triggers a sync; target is prompted,
        # and our stubbed choice returns "all".
        code, _ = _run(SkillsCommand, app, ["--prune"])
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()

    def test_target_flag_implies_sync(self, app, tmp_path):
        code, _ = _run(SkillsCommand, app, ["--target=claude"])
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()

    def test_sync_prompts_for_target_when_omitted(self, app, tmp_path):
        code, _ = _run(SkillsCommand, app, ["--sync"], choice="claude")
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_unknown_target_reports_error(self, app):
        code, lines = _run(SkillsCommand, app, ["--sync", "--target=codex"])
        # Unknown target is reported as a message, not a non-zero exit.
        assert code == 0
        assert any("Unknown target" in l for l in lines)

    def test_sync_no_skills_exits_gracefully(self, empty_app):
        code, lines = _run(SkillsCommand, empty_app, ["--sync", "--target=claude"])
        assert code == 0
        assert any("No skills" in l for l in lines)

    def test_sync_prune_removes_stale_skill(self, app, tmp_path):
        # Pre-create a synced skill that no provider declares anymore.
        stale = tmp_path / ".claude" / "skills" / "old-skill"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("stale")

        _run(SkillsCommand, app, ["--sync", "--target=claude", "--prune"])

        assert not stale.exists()
        assert (tmp_path / ".claude" / "skills" / "database" / "SKILL.md").exists()

    def test_sync_force_overwrites_existing_stub(self, app, tmp_path):
        dest = tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("user edited stub")

        _run(SkillsCommand, app, ["--sync", "--target=claude", "--force"])

        assert "user edited stub" not in dest.read_text()
