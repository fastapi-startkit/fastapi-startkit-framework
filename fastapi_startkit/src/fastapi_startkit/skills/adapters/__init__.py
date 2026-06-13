"""Adapter layer for rendering canonical skills into agent-specific formats."""

from .base import BaseAdapter
from .claude import ClaudeAdapter
from .gemini import GeminiAdapter

__all__ = ["BaseAdapter", "ClaudeAdapter", "GeminiAdapter"]
