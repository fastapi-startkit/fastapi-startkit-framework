"""Tests for SkillParser — front-matter parsing and SKILL.md → Skill loading."""

from __future__ import annotations

from pathlib import Path

from fastapi_startkit.skills.parser import Skill, SkillParser


def _write(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_basic():
    text = "---\nname: fastapi\ndescription: Apply for FastAPI code.\n---\nBody content here.\n"
    meta, body = SkillParser.parse_frontmatter(text)
    assert meta["name"] == "fastapi"
    assert meta["description"] == "Apply for FastAPI code."
    assert "Body content here." in body


def test_parse_frontmatter_missing_fence():
    text = "No front-matter here."
    meta, body = SkillParser.parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_unclosed_fence():
    meta, body = SkillParser.parse_frontmatter("---\nname: oops\n")
    assert meta == {}


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------


def test_parse_returns_skill_with_fields(tmp_path):
    path = _write(
        tmp_path,
        "SKILL.md",
        "---\nname: routing\ndescription: Routing helpers.\n---\nUse `Router`.\n",
    )
    skill = SkillParser().parse(path, provider_key="fastapi")
    assert isinstance(skill, Skill)
    assert skill.name == "routing"
    assert skill.description == "Routing helpers."
    assert "Use `Router`." in skill.body
    assert skill.provider_key == "fastapi"
    assert skill.path == path


def test_parse_falls_back_to_parent_dir_name(tmp_path):
    path = _write(tmp_path, "fallback-skill/SKILL.md", "No front-matter.")
    skill = SkillParser().parse(path)
    assert skill is not None
    assert skill.name == "fallback-skill"


def test_parse_returns_none_for_missing_file(tmp_path):
    assert SkillParser().parse(tmp_path / "does-not-exist.md") is None


def test_parse_captures_extra_metadata(tmp_path):
    path = _write(
        tmp_path,
        "SKILL.md",
        "---\nname: s\ndescription: d\nversion: 2\n---\nBody.\n",
    )
    skill = SkillParser().parse(path)
    assert skill.metadata == {"version": 2}


def test_parse_default_provider_key(tmp_path):
    path = _write(tmp_path, "SKILL.md", "---\nname: s\ndescription: d\n---\n")
    skill = SkillParser().parse(path)
    assert skill.provider_key == "fastapi-startkit"
