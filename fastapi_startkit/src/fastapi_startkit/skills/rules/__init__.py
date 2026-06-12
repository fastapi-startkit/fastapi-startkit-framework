"""Rules sub-system — per-topic rule files nested inside each skill directory.

Layout: .ai/fastapi-startkit/skill/<skill-name>/rules/<rule-name>.md
"""

from .registry import Rule, RulesRegistry, SKILLS_BASE_PATH

__all__ = ["Rule", "RulesRegistry", "SKILLS_BASE_PATH"]
