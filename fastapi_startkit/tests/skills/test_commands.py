"""Tests for the ai:skills command (list + sync).

The skills module is provider-driven: a provider declares skills by having a
``provider_key`` that appears in :attr:`SkillRegistry.skills`. The real
``FastAPIProvider`` declares the ``fastapi`` skill, so the tests register it
(rather than a stub provider). ``AISkillProvider`` binds the registry the
command resolves.

The command is driven through Cleo's :class:`CommandTester`, so option parsing
and IO go through the real machinery. Tests run non-interactively, so an omitted
``--target`` resolves to the prompt's default ("all") instead of blocking.
"""

from __future__ import annotations

import pytest
from cleo.testers.command_tester import CommandTester

from fastapi_startkit.application import Application
from fastapi_startkit.fastapi.providers.fastapi_provider import FastAPIProvider
from fastapi_startkit.skills import AISkillProvider
from fastapi_startkit.skills.commands import SkillsCommand

#: Claude skill dir for the fastapi skill (from the stub's front-matter name).
FASTAPI_SKILL = "fastapi-startkit"


@pytest.fixture(autouse=True)
def restore_container():
    from fastapi_startkit.container.container import Container

    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    """App with the real skill-declaring FastAPIProvider and a bound registry."""
    return Application(
        base_path=tmp_path,
        env="testing",
        providers=[AISkillProvider, FastAPIProvider],
    )


@pytest.fixture
def empty_app(tmp_path):
    """App with no skill-declaring providers (registry still bound)."""
    return Application(base_path=tmp_path, env="testing", providers=[AISkillProvider])


def run(app, argv: str = "") -> CommandTester:
    """Execute ai:skills with *argv* against *app* and return the tester."""
    command = SkillsCommand()
    command.set_container(app)
    tester = CommandTester(command)
    tester.execute(argv, interactive=False)
    return tester


# ===========================================================================
# ai:skills --list
# ===========================================================================


class TestSkillsListCommand:
    def test_list_shows_declaring_providers(self, app):
        tester = run(app, "--list")
        assert tester.status_code == 0
        assert "fastapi" in tester.io.fetch_output()

    def test_list_is_default_when_no_flags(self, app):
        tester = run(app)
        assert tester.status_code == 0
        assert "fastapi" in tester.io.fetch_output()

    def test_list_no_skills_shows_message(self, empty_app):
        tester = run(empty_app, "--list")
        assert tester.status_code == 0
        assert "No skills" in tester.io.fetch_output()

    def test_command_name(self):
        assert SkillsCommand().name == "ai:skills"


# ===========================================================================
# ai:skills --sync
# ===========================================================================


class TestSkillsSyncCommand:
    def test_sync_claude_publishes_stub_and_skill_file(self, app, tmp_path):
        tester = run(app, "--sync --target=claude")
        assert tester.status_code == 0
        # Stub is copied into the project's .ai/ tree.
        assert (tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md").exists()
        # ClaudeAdapter writes one dir per skill name (from stub front-matter).
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_gemini_only(self, app, tmp_path):
        tester = run(app, "--sync --target=gemini")
        assert tester.status_code == 0
        assert (tmp_path / "GEMINI.md").exists()
        assert not (tmp_path / ".claude").exists()

    def test_sync_all_writes_both(self, app, tmp_path):
        tester = run(app, "--sync --target=all")
        assert tester.status_code == 0
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_omitted_target_defaults_to_all(self, app, tmp_path):
        # Non-interactive, so the target prompt resolves to its default ("all").
        tester = run(app, "--sync")
        assert tester.status_code == 0
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_prune_implies_sync(self, app, tmp_path):
        # --prune alone (no --sync) still triggers a sync.
        tester = run(app, "--prune")
        assert tester.status_code == 0
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()

    def test_target_flag_implies_sync(self, app, tmp_path):
        tester = run(app, "--target=claude")
        assert tester.status_code == 0
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()

    def test_sync_unknown_target_reports_error(self, app):
        tester = run(app, "--sync --target=codex")
        # Unknown target is reported as a message, not a non-zero exit.
        assert tester.status_code == 0
        assert "Unknown target" in tester.io.fetch_output()

    def test_sync_no_skills_exits_gracefully(self, empty_app):
        tester = run(empty_app, "--sync --target=claude")
        assert tester.status_code == 0
        assert "No skills" in tester.io.fetch_output()

    def test_sync_prune_removes_stale_skill(self, app, tmp_path):
        # Pre-create a synced skill that no provider declares anymore.
        stale = tmp_path / ".claude" / "skills" / "old-skill"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("stale")

        run(app, "--sync --target=claude --prune")

        assert not stale.exists()
        assert (tmp_path / ".claude" / "skills" / FASTAPI_SKILL / "SKILL.md").exists()

    def test_sync_force_overwrites_existing_stub(self, app, tmp_path):
        dest = tmp_path / ".ai" / "fastapi-startkit" / "fastapi" / "SKILL.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("user edited stub")

        run(app, "--sync --target=claude --force")

        assert "user edited stub" not in dest.read_text()
