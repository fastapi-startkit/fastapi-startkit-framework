"""Tests for the AgentResponse dataclass."""

import unittest

from fastapi_startkit.ai.response import AgentResponse


class TestAgentResponse(unittest.TestCase):
    def test_text_returns_content(self):
        response = AgentResponse(content="Hello, world!")
        self.assertEqual(response.text(), "Hello, world!")

    def test_text_returns_empty_string_when_no_content(self):
        response = AgentResponse()
        self.assertEqual(response.text(), "")

    def test_text_returns_multiline_content(self):
        content = "Line 1\nLine 2\nLine 3"
        response = AgentResponse(content=content)
        self.assertEqual(response.text(), content)

    def test_json_parses_content_as_json(self):
        response = AgentResponse(content='{"key": "value", "number": 42}')
        parsed = response.json()
        self.assertEqual(parsed, {"key": "value", "number": 42})

    def test_json_parses_list_content(self):
        response = AgentResponse(content="[1, 2, 3]")
        self.assertEqual(response.json(), [1, 2, 3])

    def test_json_parses_nested_object(self):
        response = AgentResponse(content='{"nested": {"a": 1}}')
        self.assertEqual(response.json()["nested"]["a"], 1)

    def test_json_raises_on_invalid_content(self):
        response = AgentResponse(content="not valid json")
        with self.assertRaises(Exception):  # json.JSONDecodeError
            response.json()

    def test_json_raises_on_empty_content(self):
        response = AgentResponse(content="")
        with self.assertRaises(Exception):
            response.json()

    def test_str_returns_content(self):
        response = AgentResponse(content="My response text")
        self.assertEqual(str(response), "My response text")

    def test_str_returns_empty_string_when_no_content(self):
        response = AgentResponse()
        self.assertEqual(str(response), "")

    def test_str_works_in_f_string(self):
        response = AgentResponse(content="hello")
        self.assertEqual(f"Result: {response}", "Result: hello")

    def test_bool_is_true_when_content_non_empty(self):
        response = AgentResponse(content="some text")
        self.assertIs(bool(response), True)

    def test_bool_is_false_when_content_empty(self):
        response = AgentResponse(content="")
        self.assertIs(bool(response), False)

    def test_bool_is_false_when_content_not_set(self):
        response = AgentResponse()
        self.assertIs(bool(response), False)

    def test_bool_is_true_with_whitespace_content(self):
        """A response with only whitespace still evaluates as truthy (non-empty string)."""
        response = AgentResponse(content="   ")
        self.assertIs(bool(response), True)

    def test_bool_usable_in_conditional(self):
        response = AgentResponse(content="text")
        self.assertTrue(response)

        empty = AgentResponse(content="")
        self.assertFalse(empty)

    def test_tool_calls_default_to_empty_list(self):
        response = AgentResponse()
        self.assertEqual(response.tool_calls, [])

    def test_usage_defaults_to_empty_dict(self):
        response = AgentResponse()
        self.assertEqual(response.usage, {})

    def test_raw_defaults_to_none(self):
        response = AgentResponse()
        self.assertIsNone(response.raw)

    def test_all_fields_can_be_set(self):
        raw_obj = object()
        response = AgentResponse(
            content="text",
            tool_calls=[{"name": "search", "input": {"q": "test"}}],
            usage={"input": 10, "output": 20},
            raw=raw_obj,
        )
        self.assertEqual(response.content, "text")
        self.assertEqual(response.tool_calls, [{"name": "search", "input": {"q": "test"}}])
        self.assertEqual(response.usage, {"input": 10, "output": 20})
        self.assertIs(response.raw, raw_obj)
