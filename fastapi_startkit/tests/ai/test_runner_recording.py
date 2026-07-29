"""The Runner must capture the full per-turn interaction (task #1251).

A turn that calls a tool has to preserve the model's requested tool calls, the
tool's response and per-call latency, and the model usage — not collapse to the
last tool-result message (which drops ``tool_calls`` entirely).
"""

import unittest

from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.tools import tool

from fastapi_startkit.ai import state as ai_state
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.runner import Runner


@tool
def echo_tool(x: str) -> str:
    """Echo the input back."""
    return f"echoed:{x}"


class EchoAgent(Agent):
    def tools(self):
        return [echo_tool]


class FakeModel:
    def __init__(self, response):
        self._response = response

    async def ainvoke(self, messages):
        return self._response


def _runner_with_model(response):
    agent = EchoAgent()
    runner = Runner(agent)
    runner._build_model = lambda *a, **k: FakeModel(response)  # type: ignore[method-assign]
    return runner


class TestRunnerCapturesToolTurn(unittest.IsolatedAsyncioTestCase):
    def _tool_ai_message(self):
        return LCAIMessage(
            content="",
            tool_calls=[{"name": "echo_tool", "args": {"x": "hi"}, "id": "c1", "type": "tool_call"}],
            usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        )

    async def test_tool_calls_are_preserved_not_dropped(self):
        runner = _runner_with_model(self._tool_ai_message())

        response = await runner.run("hi")

        self.assertEqual([tc["name"] for tc in ai_state.tool_calls(response)], ["echo_tool"])

    async def test_tool_response_and_latency_are_captured(self):
        runner = _runner_with_model(self._tool_ai_message())

        response = await runner.run("hi")

        events = ai_state.tool_events(response)
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["name"], "echo_tool")
        self.assertEqual(event["content"], "echoed:hi")
        self.assertGreaterEqual(event["response_time"], 0)

    async def test_usage_comes_from_the_requesting_ai_message(self):
        runner = _runner_with_model(self._tool_ai_message())

        response = await runner.run("hi")

        self.assertEqual(ai_state.usage(response), {"input": 10, "output": 5})

    async def test_messages_are_an_ordered_human_ai_then_tool(self):
        runner = _runner_with_model(self._tool_ai_message())

        response = await runner.run("hi")

        kinds = [m.type for m in response["messages"]]
        self.assertEqual(kinds, ["human", "ai", "tool"])
        self.assertEqual(response["messages"][1].tool_calls[0]["name"], "echo_tool")
        self.assertEqual(response["messages"][2].content, "echoed:hi")
        self.assertGreaterEqual(response["messages"][1].additional_kwargs["response_time"], 0)


class TestRunnerPlainTurn(unittest.IsolatedAsyncioTestCase):
    async def test_plain_answer_records_a_single_ai_message(self):
        message = LCAIMessage(
            content="Hi there!", usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}
        )
        runner = _runner_with_model(message)

        response = await runner.run("hello")

        self.assertEqual(ai_state.text(response), "Hi there!")
        self.assertEqual(ai_state.tool_calls(response), [])
        self.assertEqual([m.type for m in response["messages"]], ["human", "ai"])
        self.assertEqual(response["messages"][1].content, "Hi there!")
