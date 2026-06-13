"""fastapi_startkit.skills — AI skill & rules registry and adapters.

Skills and their nested rules both live under:
    .ai/fastapi-startkit/<skill-name>/
        SKILL.md
        rules/
            <rule-name>.md

Run ``artisan skills:sync`` to deploy skills, ``artisan rules:sync`` for rules.
"""

from .registry import Skill, SkillRegistry, SKILLS_BASE_PATH, _parse_frontmatter
from .provider import SkillsServiceProvider
from .rules import Rule, RulesRegistry

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillsServiceProvider",
    "SKILLS_BASE_PATH",
    "Rule",
    "RulesRegistry",
    "_parse_frontmatter",
]
