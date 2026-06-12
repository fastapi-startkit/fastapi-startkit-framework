"""Tests for skills:sync, skills:list, rules:sync, rules:list commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.skills.registry import SkillRegistry, SKILLS_BASE_PATH
from fastapi_startkit.skills.rules.registry import RulesRegistry
from fastapi_startkit.skills.commands.sync import SkillsSyncCommand
from fastapi_startkit.skills.commands.list import SkillsListCommand
from fastapi_startkit.skills.rules.commands.sync import RulesSyncCommand
from fastapi_startkit.skills.rules.commands.list import RulesListCommand


@pytest.fixture(autouse=True)
def restore_container():
    original = Container._instance
    yield
    Container._instance = original


@pytest.fixture
def app(tmp_path):
    return Application(base_path=tmp_path, env="testing")


def _write_skill_md(tmp_path, name, description):
    skill_dir = tmp_path / SKILLS_BASE_PATH / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\nBody.\n",
        encoding="utf-8",
    )


def _write_rule_md(tmp_path, skill_name, rule_name, body="Rule body."):
    """Write a rule nested inside a skill directory."""
    rules_dir = tmp_path / SKILLS_BASE_PATH / skill_name / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / f"{rule_name}.md").write_text(body, encoding="utf-8")


def _run(cmd_class, container, args=None):
    cmd = cmd_class()
    cmd.set_container(container)
    opts = {}
    for arg in (args or []):
        if arg.startswith("--"):
            k = arg.lstrip("-").split("=")[0]
            v = arg.split("=")[1] if "=" in arg else True
            opts[k] = v
    lines = []
    cmd.option = lambda k, default=None: opts.get(k, default)
    cmd.line = lambda msg, *a, **kw: lines.append(msg)
    cmd.info = lambda msg, *a, **kw: lines.append(msg)
    return cmd.handle(), lines


# ===========================================================================
# skills:sync
# ===========================================================================

class TestSkillsSyncCommand:
    def test_sync_all_writes_claude_and_gemini(self, tmp_path, app):
        _write_skill_md(tmp_path, "orm-routing", "ORM routing")
        app.bind("skills.registry", SkillRegistry(app))
        code, _ = _run(SkillsSyncCommand, app, ["--target=all"])
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "orm-routing" / "SKILL.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_claude_only(self, tmp_path, app):
        _write_skill_md(tmp_path, "console-commands", "Commands")
        app.bind("skills.registry", SkillRegistry(app))
        _run(SkillsSyncCommand, app, ["--target=claude"])
        assert (tmp_path / ".claude" / "skills" / "console-commands" / "SKILL.md").exists()
        assert not (tmp_path / "GEMINI.md").exists()

    def test_sync_gemini_only(self, tmp_path, app):
        _write_skill_md(tmp_path, "fastapi-routing", "Routing")
        app.bind("skills.registry", SkillRegistry(app))
        _run(SkillsSyncCommand, app, ["--target=gemini"])
        assert not (tmp_path / ".claude").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_unknown_target_returns_error(self, tmp_path, app):
        app.bind("skills.registry", SkillRegistry(app))
        code, lines = _run(SkillsSyncCommand, app, ["--target=codex"])
        assert code == 1

    def test_sync_no_skills_exits_gracefully(self, tmp_path, app):
        app.bind("skills.registry", SkillRegistry(app))
        code, lines = _run(SkillsSyncCommand, app)
        assert code == 0
        assert any("No skills" in l for l in lines)

    def test_sync_prune_removes_old_skills(self, tmp_path, app):
        old_dir = tmp_path / ".claude" / "skills" / "old-skill"
        old_dir.mkdir(parents=True)
        (old_dir / "SKILL.md").write_text("old")
        _write_skill_md(tmp_path, "new-skill", "New")
        app.bind("skills.registry", SkillRegistry(app))
        _run(SkillsSyncCommand, app, ["--target=claude", "--prune"])
        assert not old_dir.exists()

    def test_command_name(self):
        assert SkillsSyncCommand().name == "skills:sync"


# ===========================================================================
# skills:list
# ===========================================================================

class TestSkillsListCommand:
    def test_list_shows_skills(self, tmp_path, app):
        _write_skill_md(tmp_path, "fastapi-routing", "FastAPI routing")
        _write_skill_md(tmp_path, "orm-queries", "ORM queries")
        app.bind("skills.registry", SkillRegistry(app))
        code, lines = _run(SkillsListCommand, app)
        assert code == 0
        out = "\n".join(lines)
        assert "fastapi-routing" in out
        assert "orm-queries" in out

    def test_list_no_skills_shows_message(self, tmp_path, app):
        app.bind("skills.registry", SkillRegistry(app))
        code, lines = _run(SkillsListCommand, app)
        assert code == 0
        assert any("No skills" in l for l in lines)

    def test_command_name(self):
        assert SkillsListCommand().name == "skills:list"


# ===========================================================================
# rules:sync  (rules nested inside skills)
# ===========================================================================

class TestRulesSyncCommand:
    def test_sync_claude_creates_nested_rule_file(self, tmp_path, app):
        _write_rule_md(tmp_path, "fastapi-best-practices", "http-client", "Always set timeout.")
        app.bind("rules.registry", RulesRegistry(app))
        code, _ = _run(RulesSyncCommand, app, ["--target=claude"])
        assert code == 0
        dest = tmp_path / ".claude" / "skills" / "fastapi-best-practices" / "rules" / "http-client.md"
        assert dest.exists()
        assert "Always set timeout." in dest.read_text()

    def test_sync_gemini_updates_gemini_md(self, tmp_path, app):
        _write_rule_md(tmp_path, "fastapi-best-practices", "http-client", "Always set timeout.")
        app.bind("rules.registry", RulesRegistry(app))
        code, _ = _run(RulesSyncCommand, app, ["--target=gemini"])
        assert code == 0
        content = (tmp_path / "GEMINI.md").read_text()
        assert "<!-- rules:start -->" in content
        assert "http-client" in content
        assert "fastapi-best-practices" in content

    def test_sync_all_writes_both(self, tmp_path, app):
        _write_rule_md(tmp_path, "orm-best-practices", "queries", "Use async ORM.")
        app.bind("rules.registry", RulesRegistry(app))
        code, _ = _run(RulesSyncCommand, app, ["--target=all"])
        assert code == 0
        assert (tmp_path / ".claude" / "skills" / "orm-best-practices" / "rules" / "queries.md").exists()
        assert (tmp_path / "GEMINI.md").exists()

    def test_sync_prune_removes_stale_rule_within_skill(self, tmp_path, app):
        # Stale rule in a skill that still has other rules
        stale = tmp_path / ".claude" / "skills" / "fastapi-best-practices" / "rules" / "old-rule.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale")
        # Only http-client is in the registry now
        _write_rule_md(tmp_path, "fastapi-best-practices", "http-client", "body")
        app.bind("rules.registry", RulesRegistry(app))
        _run(RulesSyncCommand, app, ["--target=claude", "--prune"])
        assert not stale.exists()

    def test_prune_removes_skill_dir_removes_its_rules_too(self, tmp_path, app):
        """When ClaudeAdapter prunes a skill, its nested rules/ are gone too."""
        from fastapi_startkit.skills.adapters.claude import ClaudeAdapter
        from fastapi_startkit.skills.registry import Skill
        # Simulate a previously synced skill with a nested rule
        old_skill = tmp_path / ".claude" / "skills" / "dead-skill"
        old_rule = old_skill / "rules" / "some-rule.md"
        old_rule.parent.mkdir(parents=True)
        old_rule.write_text("rule content")
        (old_skill / "SKILL.md").write_text("---\nname: dead-skill\n---\n")

        # Prune with an empty skills list removes the whole dir (including rules/)
        adapter = ClaudeAdapter(base_path=tmp_path)
        messages = adapter.prune([])
        assert not old_skill.exists()
        assert any("Pruned" in m for m in messages)

    def test_no_rules_exits_gracefully(self, tmp_path, app):
        app.bind("rules.registry", RulesRegistry(app))
        code, lines = _run(RulesSyncCommand, app)
        assert code == 0
        assert any("No rules" in l for l in lines)

    def test_unknown_target_returns_error(self, tmp_path, app):
        app.bind("rules.registry", RulesRegistry(app))
        code, _ = _run(RulesSyncCommand, app, ["--target=codex"])
        assert code == 1

    def test_command_name(self):
        assert RulesSyncCommand().name == "rules:sync"


# ===========================================================================
# rules:list
# ===========================================================================

class TestRulesListCommand:
    def test_list_shows_rules(self, tmp_path, app):
        _write_rule_md(tmp_path, "fastapi-best-practices", "http-client")
        _write_rule_md(tmp_path, "fastapi-best-practices", "validation")
        app.bind("rules.registry", RulesRegistry(app))
        code, lines = _run(RulesListCommand, app)
        assert code == 0
        out = "\n".join(lines)
        assert "http-client" in out
        assert "validation" in out

    def test_list_shows_synced_status(self, tmp_path, app):
        _write_rule_md(tmp_path, "fastapi-best-practices", "http-client")
        dest = tmp_path / ".claude" / "skills" / "fastapi-best-practices" / "rules" / "http-client.md"
        dest.parent.mkdir(parents=True)
        dest.write_text("synced content")
        app.bind("rules.registry", RulesRegistry(app))
        _, lines = _run(RulesListCommand, app)
        assert "synced" in "\n".join(lines)

    def test_no_rules_message(self, tmp_path, app):
        app.bind("rules.registry", RulesRegistry(app))
        _, lines = _run(RulesListCommand, app)
        assert any("No rules" in l for l in lines)

    def test_command_name(self):
        assert RulesListCommand().name == "rules:list"
