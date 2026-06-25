"""Declarative class decorators for Agent configuration."""

from __future__ import annotations


def provider(name: str):
    """Set the LLM provider: 'anthropic', 'openai', 'google', etc."""

    def decorator(cls):
        cls.provider = name
        return cls

    return decorator


def model(name: str = ""):
    """Set the model identifier (e.g. 'claude-sonnet-4-6', 'gpt-4o')."""

    def decorator(cls):
        cls.model = name
        return cls

    return decorator


def max_steps(n: int = 10):
    """Maximum agentic loop iterations before stopping."""

    def decorator(cls):
        cls.max_steps = n
        return cls

    return decorator


def max_tokens(n: int = 4096):
    """Maximum output tokens per response."""

    def decorator(cls):
        cls.max_tokens = n
        return cls

    return decorator


def timeout(seconds: float = 30.0):
    """Request timeout in seconds."""

    def decorator(cls):
        cls.timeout = seconds
        return cls

    return decorator


def top_p(value: float = 1.0):
    """Top-p nucleus sampling parameter."""

    def decorator(cls):
        cls.top_p = value
        return cls

    return decorator


