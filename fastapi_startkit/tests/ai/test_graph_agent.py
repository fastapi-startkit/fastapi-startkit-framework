"""Tests for GraphAgent — a LangGraph tool-calling loop layered on Agent.

Uses the same ``Agent.fake()`` model-swap as the other agent tests: scripted
turns drive the real graph (message assembly -> llm node -> tool node -> loop),
only the model at the bottom is a fake.
"""

import unittest

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from fastapi_startkit.ai import state as ai_state
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.graph import GraphAgent, GraphRunner, AgentState


@tool
def add(a: int, b: int) -> int:
    """Add ``a`` and ``b``."""
    return a + b


class MathAgent(GraphAgent):
    def instructions(self):
        return "You are a helpful assistant tasked with performing arithmetic."

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


# A tool-calling turn (add 3 + 4), then the model's final natural-language answer.
SCRIPT = [
    AIMessage(content="", tool_calls=[{"name": "add", "args": {"a": 3, "b": 4}, "id": "call_0"}]),
    "The answer is 7",
]


class TestGraphAgent(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        Ai.reset_fakes()

    async def test_prompt_runs_the_tool_loop(self):
        with MathAgent.fake(list(SCRIPT)):
            response = await MathAgent().prompt("Add 3 and 4.")

        self.assertEqual(ai_state.text(response), "The answer is 7")
        self.assertTrue(any(call["name"] == "add" for call in ai_state.tool_calls(response)))

    async def test_prompt_executes_the_tool_and_feeds_it_back(self):
        with MathAgent.fake(list(SCRIPT)):
            response = await MathAgent().prompt("Add 3 and 4.")

        # The add tool ran (3 + 4) and its result was fed back for the final turn.
        add_call = next(call for call in ai_state.tool_calls(response) if call["name"] == "add")
        self.assertEqual(add_call["args"], {"a": 3, "b": 4})

    async def test_stream_yields_the_final_answer_token_by_token(self):
        with MathAgent.fake(["The answer is 7"]):
            events = [e async for e in MathAgent().stream("What is 3 plus 4?")]

        chunks = [
            e["data"]["chunk"].text for e in events if e["event"] == "on_chat_model_stream" and e["data"]["chunk"].text
        ]
        self.assertEqual("".join(chunks), "The answer is 7")
        self.assertGreater(len(chunks), 1)
        # The graph emits real astream_events: a root chain wraps the model turn.
        self.assertEqual(events[0]["event"], "on_chain_start")
        self.assertEqual(events[-1]["event"], "on_chain_end")

    async def test_records_the_prompt_call(self):
        with MathAgent.fake(["7"]) as agent:
            await agent.prompt("Add 3 and 4.")
            agent.assert_prompted(times=1)

    async def test_middleware_wraps_the_llm_call(self):
        recorder = RecordingMiddleware()

        class MiddlewareAgent(MathAgent):
            def middleware(self):
                return [recorder]

        with MiddlewareAgent.fake(["The answer is 7"]):
            response = await MiddlewareAgent().prompt("What is 3 plus 4?")

        self.assertEqual(ai_state.text(response), "The answer is 7")
        self.assertEqual(recorder.before, 1, "middleware handle() was never invoked")
        self.assertEqual(recorder.after, 1, "middleware after-hook never fired")


class RecordingMiddleware:
    """A middleware that counts how often it wraps a model call."""

    def __init__(self):
        self.before = 0
        self.after = 0

    def handle(self, model, handler):
        self.before += 1
        return handler(model).then(lambda _final: self._record_after())

    def _record_after(self):
        self.after += 1
