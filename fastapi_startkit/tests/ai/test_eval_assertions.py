"""Tests for the Pest-evals-style assertions on the agent test double.

Deterministic checks:
    agent.assert_json()
    agent.assert_follow_trajectory(["lookup_order", "create_return", "issue_refund"])

LLM-judge checks (judge mocked here); the judge provider/model default to the
agent under test and verdicts are cached in a sidecar file next to the cassette:
    agent.assert_satisfy("The response stays on topic.")
    agent.assert_relevant()
    agent.assert_safe()
    agent.assert_prompt_judged("The prompt asks for a summary.")
    agent.assert_response_judged(expectation="...")  # grades the whole response
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from langchain_core.messages import AIMessage

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.testing import AgentRecordFake


class EvalAgent(Agent):
    provider = "openai"
    model = "gpt-4o-mini"


def _ai(content: str = "", tool_calls: list | None = None) -> AIMessage:
    return AIMessage(content=content, tool_calls=tool_calls or [], additional_kwargs={"response_time": 1.0})


def _state(content: str = "", tool_calls: list | None = None) -> dict:
    return {"messages": [_ai(content, tool_calls)]}


def _tool_call(name: str, **args) -> dict:
    return {"name": name, "args": args, "id": name, "type": "tool_call"}


def _fake_prompt(responses: list):
    queue = list(responses)

    async def prompt(agent_self, message, **kwargs):
        return queue.pop(0)

    return mock.patch.object(EvalAgent, "prompt", prompt)


def _approve(**extra):
    return mock.patch.object(AgentRecordFake, "_judge_live", mock.AsyncMock(return_value={"passed": True, **extra}))


class TestDeterministicEvals(unittest.IsolatedAsyncioTestCase):
    async def test_assert_json_passes_for_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state('{"city": "Rome"}')]):
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("give me json")
                agent.assert_json()

    async def test_assert_json_fails_for_non_json(self):
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("Rome is the capital.")]):
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_json()

    async def test_follow_trajectory_matches_ordered_tool_calls(self):
        responses = [
            _state("", [_tool_call("lookup_order")]),
            _state("", [_tool_call("create_return")]),
            _state("done", [_tool_call("issue_refund")]),
        ]
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt(responses):
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("a")
                await agent.prompt("b")
                await agent.prompt("c")
                agent.assert_follow_trajectory(["lookup_order", "create_return", "issue_refund"])

    async def test_follow_trajectory_fails_on_mismatch(self):
        responses = [_state("", [_tool_call("lookup_order")]), _state("", [_tool_call("issue_refund")])]
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt(responses):
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("a")
                await agent.prompt("b")
                with self.assertRaises(AssertionError):
                    agent.assert_follow_trajectory(["lookup_order", "create_return", "issue_refund"])


class TestJudgedEvals(unittest.IsolatedAsyncioTestCase):
    async def test_assert_satisfy_passes_when_judge_approves(self):
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("Rome")]), _approve():
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("capital of italy?")
                await agent.assert_satisfy("The answer names Rome.")

    async def test_assert_satisfy_fails_when_judge_rejects(self):
        reject = mock.patch.object(
            AgentRecordFake, "_judge_live", mock.AsyncMock(return_value={"passed": False, "reasoning": "off topic"})
        )
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("Paris")]), reject:
            with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("capital of italy?")
                with self.assertRaises(AssertionError):
                    await agent.assert_satisfy("The answer names Rome.")

    async def test_relevant_defaults_model_and_provider_to_agent_and_grades_prompt(self):
        judge = mock.AsyncMock(return_value={"passed": True})
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("Rome is the capital.")]):
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("What is the capital of Italy?")
                    await agent.assert_relevant()

        model, expectation, content, provider = judge.call_args.args
        self.assertEqual(model, "gpt-4o-mini")
        self.assertEqual(provider, "openai")
        self.assertIn("What is the capital of Italy?", expectation)
        self.assertIn("Rome", content)

    async def test_safe_uses_a_safety_expectation(self):
        judge = mock.AsyncMock(return_value={"passed": True})
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("Here is a friendly answer.")]):
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("hi")
                    await agent.assert_safe()

        _, expectation, _, _ = judge.call_args.args
        self.assertIn("safe", expectation.lower())

    async def test_prompt_judged_grades_the_prompt_not_the_response(self):
        judge = mock.AsyncMock(return_value={"passed": True})
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt([_state("some answer")]):
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("Please summarize the quarterly report")
                    await agent.assert_prompt_judged("The prompt asks for a summary.")

        _, _, content, _ = judge.call_args.args
        self.assertEqual(content, "Please summarize the quarterly report")

    async def test_response_judged_grades_the_whole_response_including_tool_calls(self):
        judge = mock.AsyncMock(return_value={"passed": True})
        responses = [_state("", [_tool_call("job_search_tool", query="python")])]
        with tempfile.TemporaryDirectory() as tmp, _fake_prompt(responses):
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with EvalAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("find python jobs")
                    await agent.assert_response_judged(expectation="It calls the job search tool.")

        _, _, content, _ = judge.call_args.args
        self.assertIn("job_search_tool", content)

    async def test_verdicts_cached_in_sidecar_file_not_the_cassette(self):
        judge = mock.AsyncMock(return_value={"passed": True, "reasoning": "ok"})
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with _fake_prompt([_state("Rome")]):
                with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                    with EvalAgent.record(cassette) as agent:
                        await agent.prompt("capital?")
                        await agent.assert_satisfy("names Rome")
                        await agent.assert_satisfy("names Rome")

            judge.assert_called_once()  # second call served from the sidecar cache

            sidecar = os.path.join(tmp, "c.judge.json")
            self.assertTrue(os.path.exists(sidecar))
            with open(cassette) as f:
                cassette_store = json.load(f)
            self.assertFalse(any(k.startswith("judge:") for k in cassette_store))
            with open(sidecar) as f:
                judge_store = json.load(f)
            self.assertTrue(any(k.startswith("judge:") for k in judge_store))


if __name__ == "__main__":
    unittest.main()
