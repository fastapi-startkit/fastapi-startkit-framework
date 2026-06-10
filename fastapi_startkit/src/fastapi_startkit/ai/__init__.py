"""FastAPI Startkit AI module.

Provides a Laravel-inspired declarative API for building AI agents backed
by Anthropic, OpenAI, or Google provider SDKs.
"""

from .agent import Agent
from .config import AIConfig, AnthropicConfig, GoogleConfig, OpenAIConfig
from .decorators import max_steps, max_tokens, memory, model, provider, timeout, top_p
from .document import Document
from .providers.ai_provider import AIProvider
from .response import AgentResponse, AgentSnapshot

__all__ = [
    "Agent",
    "AgentResponse",
    "AgentSnapshot",
    "AIConfig",
    "AIProvider",
    "AnthropicConfig",
    "Document",
    "GoogleConfig",
    "OpenAIConfig",
    "max_steps",
    "max_tokens",
    "memory",
    "model",
    "provider",
    "timeout",
    "top_p",
]
