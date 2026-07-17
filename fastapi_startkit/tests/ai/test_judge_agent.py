"""Tests for JudgeAgent — grades a response against an expectation.

It's a plain Agent whose ``schema()`` is a ``Verdict`` model, so the model's
JSON reply is turned into a typed result through the standard structured-output
path (``response.parsed``) — no hand-rolled verdict parsing.
"""

import os
import tempfile
import unittest
from unittest import mock

from langchain_core.messages import AIMessage

from fastapi_startkit.ai.judge import JudgeAgent, Verdict
from fastapi_startkit.ai.response import AgentResponse


class TestJudgeAgent(unittest.IsolatedAsyncioTestCase):
    async def test_judge_returns_a_passing_verdict_dict(self):
        with JudgeAgent.fake(['{"passed": true, "reasoning": "Greets the user politely."}']):
            result = await JudgeAgent().judge("The llm should respond with greetings", "Hello there!")

        self.assertEqual(result, {"passed": True, "reasoning": "Greets the user politely."})

    async def test_judge_returns_a_failing_verdict(self):
        with JudgeAgent.fake(['{"passed": false, "reasoning": "Not a greeting."}']):
            result = await JudgeAgent().judge("greet", "Completely unrelated")

        self.assertFalse(result["passed"])

    def test_schema_is_the_verdict_model(self):
        self.assertIs(JudgeAgent().schema(), Verdict)

    async def test_judge_feeds_expectation_and_response_to_the_model(self):
        seen = {}

        class Capturing:
            def bind_tools(self, tools, **kwargs):
                return self

            async def ainvoke(self, messages):
                seen["messages"] = messages
                return AIMessage(content='{"passed": true, "reasoning": "ok"}')

        with mock.patch.object(JudgeAgent, "_build_model", lambda self, *a, **k: Capturing()):
            await JudgeAgent().judge("The llm should respond with greetings", "Hello there!")

        blob = " ".join(str(getattr(m, "content", m)) for m in seen["messages"])
        self.assertIn("The llm should respond with greetings", blob)
        self.assertIn("Hello there!", blob)

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
