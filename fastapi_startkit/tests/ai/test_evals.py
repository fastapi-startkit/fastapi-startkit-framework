"""Tests for TestJudgeAgent — the deterministic trajectory-match evaluator.

TestJudgeAgent compares an actual agent message trajectory against a reference
trajectory with no live LLM calls: it is pure, deterministic structural
comparison, driven entirely by data the tests construct themselves (typically
the output of Agent.fake()). Mirrors the Agent.fake()/Agent.record() testing
DSL: ``.record()`` returns a context manager yielding a callable evaluator.
"""

import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.evals import TestJudgeAgent
from fastapi_startkit.ai.response import AgentResponse


def _weather_trajectory(city: str = "San Francisco") -> list:
    return [
        HumanMessage(content=f"What is the weather in {city}?"),
        AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "get_weather", "args": {"city": city}}],
        ),
        ToolMessage(content="It is 75 degrees and sunny.", tool_call_id="call_1"),
        AIMessage(content=f"The weather in {city} is 75 degrees and sunny."),
    ]


class TestJudgeAgentConstruction(unittest.TestCase):
    def test_defaults_to_strict_mode(self):
        judge = TestJudgeAgent()
        self.assertEqual(judge.trajectory_match_mode, "strict")

    def test_accepts_each_supported_mode(self):
        for mode in ("strict", "unordered", "subset", "superset"):
            judge = TestJudgeAgent(trajectory_match_mode=mode)
            self.assertEqual(judge.trajectory_match_mode, mode)

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            TestJudgeAgent(trajectory_match_mode="fuzzy")


class TestJudgeAgentRecordContextManager(unittest.TestCase):
    def test_record_yields_callable_evaluator(self):
        with TestJudgeAgent().record() as evaluator:
            self.assertTrue(callable(evaluator))

    def test_evaluation_result_is_subscriptable_with_score_key(self):
        trajectory = _weather_trajectory()
        with TestJudgeAgent(trajectory_match_mode="strict").record() as evaluator:
            evaluation = evaluator(outputs=trajectory, reference_outputs=trajectory)

        self.assertIs(evaluation["score"], True)
        self.assertEqual(evaluation["key"], "trajectory_strict_match")
        self.assertIn("comment", evaluation)


class TestStrictTrajectoryMatch(unittest.TestCase):
    def setUp(self):
        self.judge = TestJudgeAgent(trajectory_match_mode="strict")

    def _evaluate(self, outputs, reference_outputs):
        with self.judge.record() as evaluator:
            return evaluator(outputs=outputs, reference_outputs=reference_outputs)

    def test_identical_trajectory_matches(self):
        trajectory = _weather_trajectory()
        evaluation = self._evaluate(trajectory, trajectory)
        self.assertIs(evaluation["score"], True)

    def test_matches_even_when_final_message_content_differs(self):
        reference = _weather_trajectory()
        outputs = _weather_trajectory()
        outputs[-1] = AIMessage(content="Completely different wording, still sunny.")
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], True)

    def test_fails_when_tool_call_args_differ(self):
        reference = _weather_trajectory(city="San Francisco")
        outputs = _weather_trajectory(city="Oakland")
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_fails_on_extra_trailing_message(self):
        reference = _weather_trajectory()
        outputs = _weather_trajectory() + [AIMessage(content="One more thing...")]
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_fails_on_missing_message(self):
        reference = _weather_trajectory()
        outputs = _weather_trajectory()[:-1]
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_fails_when_role_order_differs(self):
        reference = _weather_trajectory()
        outputs = list(reversed(_weather_trajectory()))
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_fails_when_one_side_has_tool_calls_and_other_does_not(self):
        reference = _weather_trajectory()
        outputs = _weather_trajectory()
        outputs[1] = AIMessage(content="")
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_works_with_plain_dict_messages(self):
        reference = _weather_trajectory()
        outputs = [
            {"role": "user", "content": "What is the weather in San Francisco?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "call_1", "name": "get_weather", "args": {"city": "San Francisco"}}],
            },
            {"role": "tool", "content": "It is 75 degrees and sunny.", "tool_call_id": "call_1"},
            {"role": "assistant", "content": "The weather in San Francisco is 75 degrees and sunny."},
        ]
        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], True)


class TestUnorderedTrajectoryMatch(unittest.TestCase):
    def setUp(self):
        self.judge = TestJudgeAgent(trajectory_match_mode="unordered")

    def _evaluate(self, outputs, reference_outputs):
        with self.judge.record() as evaluator:
            return evaluator(outputs=outputs, reference_outputs=reference_outputs)

    def test_same_tool_calls_in_different_message_order_matches(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [HumanMessage(content="hi"), weather_call, time_call]
        outputs = [HumanMessage(content="hi"), time_call, weather_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], True)

    def test_missing_tool_call_fails(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call, time_call]
        outputs = [weather_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)

    def test_extra_tool_call_fails(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call]
        outputs = [weather_call, time_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)


class TestSubsetTrajectoryMatch(unittest.TestCase):
    def setUp(self):
        self.judge = TestJudgeAgent(trajectory_match_mode="subset")

    def _evaluate(self, outputs, reference_outputs):
        with self.judge.record() as evaluator:
            return evaluator(outputs=outputs, reference_outputs=reference_outputs)

    def test_output_tool_calls_within_reference_matches(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call, time_call]
        outputs = [weather_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], True)

    def test_output_tool_call_not_in_reference_fails(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call]
        outputs = [weather_call, time_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)


class TestSupersetTrajectoryMatch(unittest.TestCase):
    def setUp(self):
        self.judge = TestJudgeAgent(trajectory_match_mode="superset")

    def _evaluate(self, outputs, reference_outputs):
        with self.judge.record() as evaluator:
            return evaluator(outputs=outputs, reference_outputs=reference_outputs)

    def test_output_contains_all_reference_tool_calls_plus_extra_matches(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call]
        outputs = [weather_call, time_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], True)

    def test_output_missing_a_required_reference_tool_call_fails(self):
        weather_call = AIMessage(content="", tool_calls=[{"id": "1", "name": "get_weather", "args": {"city": "SF"}}])
        time_call = AIMessage(content="", tool_calls=[{"id": "2", "name": "get_time", "args": {"tz": "PT"}}])

        reference = [weather_call, time_call]
        outputs = [weather_call]

        evaluation = self._evaluate(outputs, reference)
        self.assertIs(evaluation["score"], False)


class SimpleAgent(Agent):
    pass


class TestJudgeAgentWithAgentFakeOutput(unittest.TestCase):
    """Demonstrates the intended workflow: Agent.fake() drives deterministic
    output with no live LLM call, and TestJudgeAgent judges the resulting
    trajectory against a reference."""

    async def _fake_response(self) -> AgentResponse:
        agent = SimpleAgent()
        with SimpleAgent.fake(["It is sunny in San Francisco."]):
            return await agent.prompt("What is the weather in San Francisco?")

    def test_fake_agent_reply_matches_reference_trajectory_in_strict_mode(self):
        import asyncio

        response = asyncio.run(self._fake_response())

        outputs = [
            HumanMessage(content="What is the weather in San Francisco?"),
            AIMessage(content=response.content),
        ]
        reference_trajectory = [
            HumanMessage(content="What is the weather in San Francisco?"),
            AIMessage(content="It is sunny in San Francisco."),
        ]

        with TestJudgeAgent(trajectory_match_mode="strict").record() as evaluator:
            evaluation = evaluator(outputs=outputs, reference_outputs=reference_trajectory)

        self.assertIs(evaluation["score"], True)


class TestJudgeAgentMessagesDictInput(unittest.TestCase):
    def test_accepts_outputs_dict_with_messages_key(self):
        trajectory = _weather_trajectory()
        with TestJudgeAgent(trajectory_match_mode="strict").record() as evaluator:
            evaluation = evaluator(outputs={"messages": trajectory}, reference_outputs=trajectory)

        self.assertIs(evaluation["score"], True)


class TestJudgeAgentIsNotCollectedByPytest(unittest.TestCase):
    def test_has_test_dunder_set_to_false(self):
        self.assertFalse(getattr(TestJudgeAgent, "__test__"))


class TestSystemMessagesAreComparedByRole(unittest.TestCase):
    def test_strict_mode_compares_system_message_role(self):
        reference = [SystemMessage(content="Be concise."), HumanMessage(content="hi")]
        outputs = [SystemMessage(content="Be very concise."), HumanMessage(content="hi")]

        with TestJudgeAgent(trajectory_match_mode="strict").record() as evaluator:
            evaluation = evaluator(outputs=outputs, reference_outputs=reference)

        self.assertIs(evaluation["score"], True)
