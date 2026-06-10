"""Declarative class decorators for Agent configuration."""

from __future__ import annotations


def provider(name: str):
    """Set the LLM provider: 'anthropic', 'openai', 'google', etc."""

    def decorator(cls):
        cls._provider = name
        return cls

    return decorator


def model(name: str = ""):
    """Set the model identifier (e.g. 'claude-sonnet-4-6', 'gpt-4o')."""

    def decorator(cls):
        cls._model = name
        return cls

    return decorator


def max_steps(n: int = 10):
    """Maximum agentic loop iterations before stopping."""

    def decorator(cls):
        cls._max_steps = n
        return cls

    return decorator


def max_tokens(n: int = 4096):
    """Maximum output tokens per response."""

    def decorator(cls):
        cls._max_tokens = n
        return cls

    return decorator


def timeout(seconds: float = 30.0):
    """Request timeout in seconds."""

    def decorator(cls):
        cls._timeout = seconds
        return cls

    return decorator


def top_p(value: float = 1.0):
    """Top-p nucleus sampling parameter."""

    def decorator(cls):
        cls._top_p = value
        return cls

    return decorator


def memory(backend: str = ""):
    """Attach a named memory backend to this agent."""

    def decorator(cls):
        cls._memory_backend = backend
        return cls

    return decorator
