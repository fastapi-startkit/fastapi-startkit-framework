"""Tests for ClaudeAdapter and GeminiAdapter (task #140)."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.skills.registry import Skill
from fastapi_startkit.skills.adapters.claude import ClaudeAdapter
from fastapi_startkit.skills.adapters.gemini import GeminiAdapter, _MARKER_START, _MARKER_END


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skill(name: str, description: str = "A test skill.", body: str = "") -> Skill:
    return Skill(name=name, description=description, path=Path("/dev/null"), provider_key="test", body=body)


# ===========================================================================
# ClaudeAdapter
# ===========================================================================


class TestClaudeAdapter:
    def test_render_creates_skill_file(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        skills = [make_skill("my-skill", "Does stuff")]

        messages = adapter.render(skills)

        skill_file = tmp_path / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert "name: my-skill" in content
        assert "description: Does stuff" in content
        assert any("Synced" in m for m in messages)

    def test_render_idempotent(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        skills = [make_skill("my-skill")]

        adapter.render(skills)
        messages = adapter.render(skills)

        assert any("Unchanged" in m for m in messages)

    def test_render_updates_changed_content(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        adapter.render([make_skill("my-skill", "Old description")])
        messages = adapter.render([make_skill("my-skill", "New description")])

        skill_file = tmp_path / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert "New description" in skill_file.read_text()
        assert any("Synced" in m for m in messages)

    def test_render_includes_body(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        skills = [make_skill("qs", "Query skill", body="Use `Model.where(...)`")]
        adapter.render(skills)

        skill_file = tmp_path / ".claude" / "skills" / "qs" / "SKILL.md"
        content = skill_file.read_text()
        assert "Use `Model.where(...)`" in content

    def test_prune_removes_unlisted_skills(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        # Pre-create two skills
        adapter.render([make_skill("keep-me"), make_skill("remove-me")])

        # Render with only one skill, prune the other
        messages = adapter.prune([make_skill("keep-me")])

        assert (tmp_path / ".claude" / "skills" / "keep-me").exists()
        assert not (tmp_path / ".claude" / "skills" / "remove-me").exists()
        assert any("Pruned" in m for m in messages)

    def test_prune_noop_when_no_skills_dir(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        messages = adapter.prune([])
        assert messages == []

    def test_render_multiple_skills(self, tmp_path):
        adapter = ClaudeAdapter(base_path=tmp_path)
        skills = [make_skill("skill-a"), make_skill("skill-b"), make_skill("skill-c")]
        messages = adapter.render(skills)

        assert len(messages) == 3
        for name in ["skill-a", "skill-b", "skill-c"]:
            assert (tmp_path / ".claude" / "skills" / name / "SKILL.md").exists()


# ===========================================================================
# GeminiAdapter
# ===========================================================================


class TestGeminiAdapter:
    def test_render_creates_gemini_md(self, tmp_path):
        adapter = GeminiAdapter(base_path=tmp_path)
        skills = [make_skill("my-skill", "Does stuff")]

        messages = adapter.render(skills)

        gemini_md = tmp_path / "GEMINI.md"
        assert gemini_md.exists()
        content = gemini_md.read_text()
        assert _MARKER_START in content
        assert _MARKER_END in content
        assert "my-skill" in content
        assert "Does stuff" in content
        assert any("Synced" in m for m in messages)

    def test_render_idempotent(self, tmp_path):
        adapter = GeminiAdapter(base_path=tmp_path)
        skills = [make_skill("my-skill")]

        adapter.render(skills)
        messages = adapter.render(skills)
        assert any("Unchanged" in m for m in messages)

    def test_render_preserves_content_outside_markers(self, tmp_path):
        gemini_md = tmp_path / "GEMINI.md"
        gemini_md.write_text(
            "# My Project\n\nSome user content.\n\n"
            + _MARKER_START + "\nold skills\n" + _MARKER_END + "\n\n"
            "## Extra Section\n\nUser notes.\n"
        )

        adapter = GeminiAdapter(base_path=tmp_path)
        adapter.render([make_skill("new-skill")])

        content = gemini_md.read_text()
        assert "My Project" in content
        assert "Some user content." in content
        assert "Extra Section" in content
        assert "User notes." in content
        assert "new-skill" in content

    def test_render_appends_if_no_markers(self, tmp_path):
        gemini_md = tmp_path / "GEMINI.md"
        gemini_md.write_text("# Existing content\n\nUser authored.\n")

        adapter = GeminiAdapter(base_path=tmp_path)
        adapter.render([make_skill("appended-skill")])

        content = gemini_md.read_text()
        assert "Existing content" in content
        assert "appended-skill" in content
        assert _MARKER_START in content
        assert _MARKER_END in content

    def test_render_multiple_skills(self, tmp_path):
        adapter = GeminiAdapter(base_path=tmp_path)
        skills = [make_skill("skill-a", "First skill"), make_skill("skill-b", "Second skill")]
        adapter.render(skills)

        content = (tmp_path / "GEMINI.md").read_text()
        assert "skill-a" in content
        assert "skill-b" in content

    def test_prune_rerenders_with_fewer_skills(self, tmp_path):
        adapter = GeminiAdapter(base_path=tmp_path)
        adapter.render([make_skill("keep"), make_skill("drop")])
        adapter.prune([make_skill("keep")])

        content = (tmp_path / "GEMINI.md").read_text()
        assert "keep" in content
        assert "drop" not in content

    def test_render_updates_changed_description(self, tmp_path):
        adapter = GeminiAdapter(base_path=tmp_path)
        adapter.render([make_skill("s", "Old desc")])
        adapter.render([make_skill("s", "New desc")])

        content = (tmp_path / "GEMINI.md").read_text()
        assert "New desc" in content
        assert "Old desc" not in content
