"""Tests for Agent class decorators."""

import unittest

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


class TestAgentDecorators(unittest.TestCase):
    def test_provider_decorator_sets_provider(self):
        @provider("openai")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._provider, "openai")

    def test_provider_decorator_sets_anthropic(self):
        @provider("anthropic")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._provider, "anthropic")

    def test_provider_decorator_sets_google(self):
        @provider("google")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._provider, "google")

    def test_model_decorator_sets_model(self):
        @model("gpt-4o")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._model, "gpt-4o")

    def test_model_decorator_sets_claude_model(self):
        @model("claude-sonnet-4-6")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._model, "claude-sonnet-4-6")

    def test_max_tokens_decorator_sets_value(self):
        @max_tokens(2048)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._max_tokens, 2048)

    def test_max_tokens_decorator_overrides_default(self):
        @max_tokens(512)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._max_tokens, 512)

    def test_max_steps_decorator_sets_value(self):
        @max_steps(5)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._max_steps, 5)

    def test_max_steps_decorator_sets_one(self):
        @max_steps(1)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._max_steps, 1)

    def test_timeout_decorator_sets_seconds(self):
        @timeout(60.0)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._timeout, 60.0)

    def test_timeout_decorator_sets_fractional(self):
        @timeout(2.5)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._timeout, 2.5)

    def test_top_p_decorator_sets_value(self):
        @top_p(0.9)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._top_p, 0.9)

    def test_top_p_decorator_sets_zero(self):
        @top_p(0.0)
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._top_p, 0.0)

    def test_memory_decorator_sets_backend(self):
        @memory("redis")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._memory_backend, "redis")

    def test_memory_decorator_sets_custom_backend(self):
        @memory("postgres")
        class MyAgent(Agent):
            pass

        self.assertEqual(MyAgent._memory_backend, "postgres")

    def test_multiple_decorators_can_be_stacked(self):
        @provider("openai")
        @model("gpt-4o")
        @max_tokens(1024)
        @max_steps(3)
        @timeout(15.0)
        @top_p(0.95)
        @memory("redis")
        class FullyConfiguredAgent(Agent):
            pass

        self.assertEqual(FullyConfiguredAgent._provider, "openai")
        self.assertEqual(FullyConfiguredAgent._model, "gpt-4o")
        self.assertEqual(FullyConfiguredAgent._max_tokens, 1024)
        self.assertEqual(FullyConfiguredAgent._max_steps, 3)
        self.assertEqual(FullyConfiguredAgent._timeout, 15.0)
        self.assertEqual(FullyConfiguredAgent._top_p, 0.95)
        self.assertEqual(FullyConfiguredAgent._memory_backend, "redis")

    def test_stacking_does_not_affect_base_class(self):
        """Decorator-applied values must not leak into the Agent base class."""

        @provider("openai")
        @model("gpt-4o")
        class SubAgent(Agent):
            pass

        self.assertIsNone(Agent._provider)
        self.assertIsNone(Agent._model)

        self.assertEqual(SubAgent._provider, "openai")
        self.assertEqual(SubAgent._model, "gpt-4o")

    def test_instance_inherits_class_config(self):
        """Instantiating a decorated class reads the right config values."""

        @provider("openai")
        @max_tokens(256)
        class TinyAgent(Agent):
            pass

        agent = TinyAgent()
        self.assertEqual(agent._provider, "openai")
        self.assertEqual(agent._max_tokens, 256)
