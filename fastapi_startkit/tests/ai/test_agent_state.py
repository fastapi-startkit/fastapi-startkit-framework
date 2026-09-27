"""Tests for the state helpers over the ``{"messages": [...]}`` turn shape."""

import unittest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from fastapi_startkit.ai import state as ai_state


def _tool_turn() -> dict:
    return {
        "messages": [
            HumanMessage(content="find jobs"),
            AIMessage(
                content="",
                tool_calls=[{"name": "job_search_tool", "args": {"q": "python"}, "id": "c1", "type": "tool_call"}],
                additional_kwargs={"response_time": 12.0},
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            ),
            ToolMessage(content='[{"id": 2}]', tool_call_id="c1", additional_kwargs={"response_time": 5.0}),
        ]
    }


class TestText(unittest.TestCase):
    def test_returns_the_last_messages_content(self):
        self.assertEqual(ai_state.text(_tool_turn()), '[{"id": 2}]')

    def test_plain_turn_returns_the_ai_answer(self):
        state = {"messages": [HumanMessage(content="hi"), AIMessage(content="Hello!")]}
        self.assertEqual(ai_state.text(state), "Hello!")

    def test_empty_state_returns_empty_string(self):
        self.assertEqual(ai_state.text({}), "")
        self.assertEqual(ai_state.text(None), "")


class TestToolCalls(unittest.TestCase):
    def test_collects_calls_from_ai_messages(self):
        self.assertEqual([tc["name"] for tc in ai_state.tool_calls(_tool_turn())], ["job_search_tool"])

    def test_plain_turn_has_no_calls(self):
        self.assertEqual(ai_state.tool_calls({"messages": [AIMessage(content="hi")]}), [])


class TestToolEvents(unittest.TestCase):
    def test_joins_the_call_with_its_tool_message(self):
        (event,) = ai_state.tool_events(_tool_turn())
        self.assertEqual(event["name"], "job_search_tool")
        self.assertEqual(event["args"], {"q": "python"})
        self.assertEqual(event["id"], "c1")
        self.assertEqual(event["content"], '[{"id": 2}]')
        self.assertEqual(event["content_type"], "json")
        self.assertEqual(event["response_time"], 5.0)

    def test_falls_back_to_order_when_ids_are_missing(self):
        state = {
            "messages": [
                AIMessage(content="", tool_calls=[{"name": "echo", "args": {"x": "hi"}, "id": "c9"}]),
                ToolMessage(content="echoed:hi", tool_call_id=""),
            ]
        }
        (event,) = ai_state.tool_events(state)
        self.assertEqual(event["name"], "echo")
        self.assertEqual(event["args"], {"x": "hi"})
        self.assertEqual(event["content_type"], "text")


class TestUsageAndRuntime(unittest.TestCase):
    def test_usage_sums_ai_messages(self):
        self.assertEqual(ai_state.usage(_tool_turn()), {"input": 10, "output": 5})

    def test_runtime_sums_response_times_in_seconds(self):
        self.assertAlmostEqual(ai_state.runtime(_tool_turn()), 0.017)


class TestStructured(unittest.TestCase):
    def test_returns_the_structured_response(self):
        self.assertEqual(ai_state.structured({"structured_response": {"a": 1}}), {"a": 1})

    def test_defaults_to_none(self):
        self.assertIsNone(ai_state.structured({"messages": []}))
        self.assertIsNone(ai_state.structured(None))
