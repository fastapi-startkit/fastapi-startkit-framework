"""fastapi_startkit.skills — central AI skill registry & adapters.

Skills are defined in ``.ai/deployments/core.html`` and deployed to each
configured AI agent target via ``artisan skills:sync``.
"""

from .registry import Skill, SkillRegistry, parse_core_html, CORE_HTML_PATH
from .provider import SkillsServiceProvider

__all__ = [
    "Skill",
    "SkillRegistry",
    "SkillsServiceProvider",
    "parse_core_html",
    "CORE_HTML_PATH",
]
