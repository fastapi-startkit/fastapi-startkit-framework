"""Tests for Agent class decorators."""

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.decorators import (
    max_steps,
    max_tokens,
    memory,
    model,
    provider,
    timeout,
    top_p,
)


# ─── Decorator: @provider ──────────────────────────────────────────────────────


def test_provider_decorator_sets_provider():
    @provider("openai")
    class MyAgent(Agent):
        pass

    assert MyAgent._provider == "openai"


def test_provider_decorator_sets_anthropic():
    @provider("anthropic")
    class MyAgent(Agent):
        pass

    assert MyAgent._provider == "anthropic"


def test_provider_decorator_sets_google():
    @provider("google")
    class MyAgent(Agent):
        pass

    assert MyAgent._provider == "google"


# ─── Decorator: @model ────────────────────────────────────────────────────────


def test_model_decorator_sets_model():
    @model("gpt-4o")
    class MyAgent(Agent):
        pass

    assert MyAgent._model == "gpt-4o"


def test_model_decorator_sets_claude_model():
    @model("claude-sonnet-4-6")
    class MyAgent(Agent):
        pass

    assert MyAgent._model == "claude-sonnet-4-6"


# ─── Decorator: @max_tokens ───────────────────────────────────────────────────


def test_max_tokens_decorator_sets_value():
    @max_tokens(2048)
    class MyAgent(Agent):
        pass

    assert MyAgent._max_tokens == 2048


def test_max_tokens_decorator_overrides_default():
    @max_tokens(512)
    class MyAgent(Agent):
        pass

    assert MyAgent._max_tokens == 512


# ─── Decorator: @max_steps ────────────────────────────────────────────────────


def test_max_steps_decorator_sets_value():
    @max_steps(5)
    class MyAgent(Agent):
        pass

    assert MyAgent._max_steps == 5


def test_max_steps_decorator_sets_one():
    @max_steps(1)
    class MyAgent(Agent):
        pass

    assert MyAgent._max_steps == 1


# ─── Decorator: @timeout ──────────────────────────────────────────────────────


def test_timeout_decorator_sets_seconds():
    @timeout(60.0)
    class MyAgent(Agent):
        pass

    assert MyAgent._timeout == 60.0


def test_timeout_decorator_sets_fractional():
    @timeout(2.5)
    class MyAgent(Agent):
        pass

    assert MyAgent._timeout == 2.5


# ─── Decorator: @top_p ────────────────────────────────────────────────────────


def test_top_p_decorator_sets_value():
    @top_p(0.9)
    class MyAgent(Agent):
        pass

    assert MyAgent._top_p == 0.9


def test_top_p_decorator_sets_zero():
    @top_p(0.0)
    class MyAgent(Agent):
        pass

    assert MyAgent._top_p == 0.0


# ─── Decorator: @memory ───────────────────────────────────────────────────────


def test_memory_decorator_sets_backend():
    @memory("redis")
    class MyAgent(Agent):
        pass

    assert MyAgent._memory_backend == "redis"


def test_memory_decorator_sets_custom_backend():
    @memory("postgres")
    class MyAgent(Agent):
        pass

    assert MyAgent._memory_backend == "postgres"


# ─── Stacking multiple decorators ─────────────────────────────────────────────


def test_multiple_decorators_can_be_stacked():
    @provider("openai")
    @model("gpt-4o")
    @max_tokens(1024)
    @max_steps(3)
    @timeout(15.0)
    @top_p(0.95)
    @memory("redis")
    class FullyConfiguredAgent(Agent):
        pass

    assert FullyConfiguredAgent._provider == "openai"
    assert FullyConfiguredAgent._model == "gpt-4o"
    assert FullyConfiguredAgent._max_tokens == 1024
    assert FullyConfiguredAgent._max_steps == 3
    assert FullyConfiguredAgent._timeout == 15.0
    assert FullyConfiguredAgent._top_p == 0.95
    assert FullyConfiguredAgent._memory_backend == "redis"


def test_stacking_does_not_affect_base_class():
    """Decorator-applied values must not leak into the Agent base class."""

    @provider("openai")
    @model("gpt-4o")
    class SubAgent(Agent):
        pass

    # Base Agent must retain its own defaults
    assert Agent._provider == "anthropic"
    assert Agent._model == ""

    # Subclass has decorated values
    assert SubAgent._provider == "openai"
    assert SubAgent._model == "gpt-4o"


def test_instance_inherits_class_config():
    """Instantiating a decorated class reads the right config values."""

    @provider("openai")
    @max_tokens(256)
    class TinyAgent(Agent):
        pass

    agent = TinyAgent()
    assert agent._provider == "openai"
    assert agent._max_tokens == 256
