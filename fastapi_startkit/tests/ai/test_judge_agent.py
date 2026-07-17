"""Tests for JudgeAgent — the built-in Agent subclass that grades a
response against a natural-language expectation.

Because it's just an Agent, it gets model/provider resolution, ``fake()``,
and ``record()`` for free instead of RecordingAgent hand-rolling its own
langchain call.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai.judge import JudgeAgent
from fastapi_startkit.ai.response import AgentResponse


class TestJudgeAgent(unittest.IsolatedAsyncioTestCase):
    async def test_judge_parses_a_passing_verdict_from_the_model_response(self):
        verdict = '{"passed": true, "reasoning": "Greets the user politely."}'
        with JudgeAgent.fake([verdict]):
            judge = JudgeAgent()
            judge.model = "gpt-3.5-turbo"
            result = await judge.judge("The llm should respond with greetings", "Hello there!")

        self.assertEqual(result, {"passed": True, "reasoning": "Greets the user politely."})

    async def test_judge_parses_a_failing_verdict(self):
        verdict = '{"passed": false, "reasoning": "Not a greeting."}'
        with JudgeAgent.fake([verdict]):
            judge = JudgeAgent()
            judge.model = "gpt-3.5-turbo"
            result = await judge.judge("The llm should respond with greetings", "Completely unrelated")

        self.assertFalse(result["passed"])

    async def test_judge_tolerates_prose_around_the_json_block(self):
        verdict = 'Sure! Here is the verdict:\n{"passed": true, "reasoning": "ok"}\nHope that helps.'
        with JudgeAgent.fake([verdict]):
            judge = JudgeAgent()
            judge.model = "gpt-3.5-turbo"
            result = await judge.judge("greet", "Hello!")

        self.assertTrue(result["passed"])

    def test_prompt_includes_expectation_and_response(self):
        prompt = JudgeAgent._build_prompt("The llm should respond with greetings", "Hello there!")

        self.assertIn("The llm should respond with greetings", prompt)
        self.assertIn("Hello there!", prompt)

    def test_model_and_provider_are_plain_agent_attributes(self):
        """No custom constructor — set like any other Agent's model/provider."""
        judge = JudgeAgent()
        judge.model = "gpt-4o-mini"
        judge.provider = "openai"

        self.assertEqual(judge.model, "gpt-4o-mini")
        self.assertEqual(judge.provider, "openai")

    def test_model_and_provider_default_to_agent_defaults(self):
        judge = JudgeAgent()

        self.assertIsNone(judge.model)
        self.assertIsNone(judge.provider)

    async def test_judge_is_usable_via_the_record_fluent_dsl(self):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content='{"passed": true, "reasoning": "ok"}')

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "judge.json")
            with mock.patch.object(JudgeAgent, "_run", fake_run):
                with JudgeAgent.record(cassette) as agent:
                    response = await agent.prompt("grade this")

            self.assertIn('"passed"', response.content)
            self.assertTrue(os.path.exists(cassette))
            self.assertEqual(len(json.loads(open(cassette).read())), 1)
