"""The GraphRunner must capture the full tool-loop interaction (task #1251).

A graph turn that calls a tool records the ordered transcript
(ai -> tool_response -> ai) with tool responses and per-call latency, mirroring
the plain Runner.
"""

import unittest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.graph import AgentState, GraphAgent, GraphRunner


@tool
def add(a: int, b: int) -> int:
    """Add ``a`` and ``b``."""
    return a + b


class MathAgent(GraphAgent):
    def tools(self):
        return [add]

    async def graph(self, runner: GraphRunner):
        graph = StateGraph(AgentState)
        graph.add_node("llm", runner.llm)
        graph.add_node("tools", runner.call_tools)
        graph.add_edge(START, "llm")
        graph.add_conditional_edges("llm", runner.route, ["tools", END])
        graph.add_edge("tools", "llm")
        return graph.compile()


SCRIPT = [
    AIMessage(content="", tool_calls=[{"name": "add", "args": {"a": 3, "b": 4}, "id": "call_0"}]),
    "The answer is 7",
]


class TestGraphRunnerCapture(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        Ai.reset_fakes()

    async def test_transcript_records_the_full_tool_loop(self):
        with MathAgent.fake(list(SCRIPT)):
            response = await MathAgent().prompt("Add 3 and 4.")

        kinds = [entry["type"] for entry in response.transcript]
        self.assertEqual(kinds, ["ai", "tool_response", "ai"])

    async def test_tool_response_and_final_answer_are_captured(self):
        with MathAgent.fake(list(SCRIPT)):
            response = await MathAgent().prompt("Add 3 and 4.")

        tool_entry = next(e for e in response.transcript if e["type"] == "tool_response")
        self.assertEqual(tool_entry["content"], "7")
        self.assertGreaterEqual(tool_entry["response_time"], 0)

        self.assertEqual(response.transcript[-1].get("content"), "The answer is 7")
        self.assertEqual(len(response.tool_events), 1)
        self.assertEqual(response.tool_events[0]["name"], "add")
