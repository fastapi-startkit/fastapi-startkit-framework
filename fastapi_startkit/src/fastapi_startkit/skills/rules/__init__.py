"""Rules sub-system — per-topic coding rule files at ``rules/*.md``."""

from .registry import Rule, RulesRegistry, RULES_BASE_PATH

__all__ = ["Rule", "RulesRegistry", "RULES_BASE_PATH"]
