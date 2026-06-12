"""fastapi_startkit.skills — provider-driven AI skill registry & adapters."""

from .registry import Skill, SkillRegistry
from .provider import SkillsServiceProvider

__all__ = ["Skill", "SkillRegistry", "SkillsServiceProvider"]
