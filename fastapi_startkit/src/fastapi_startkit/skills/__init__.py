"""fastapi_startkit.skills — AI skill & rules registry and adapters.

Skills -> .ai/fastapi-startkit/skill/{name}/SKILL.md
Rules  -> rules/{name}.md

Run ``artisan skills:sync`` to deploy skills, ``artisan rules:sync`` for rules.
"""

from .registry import Skill, SkillRegistry, SKILLS_BASE_PATH, _parse_frontmatter
from .provider import SkillsServiceProvider
from .rules import Rule, RulesRegistry, RULES_BASE_PATH

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillsServiceProvider",
    "SKILLS_BASE_PATH",
    "Rule",
    "RulesRegistry",
    "RULES_BASE_PATH",
    "_parse_frontmatter",
]
