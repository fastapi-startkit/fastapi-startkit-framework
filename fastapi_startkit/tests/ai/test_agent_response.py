"""Tests for the AgentResponse dataclass."""

import pytest
from fastapi_startkit.ai.response import AgentResponse


# ─── AgentResponse.text() ─────────────────────────────────────────────────────


def test_text_returns_content():
    response = AgentResponse(content="Hello, world!")
    assert response.text() == "Hello, world!"


def test_text_returns_empty_string_when_no_content():
    response = AgentResponse()
    assert response.text() == ""


def test_text_returns_multiline_content():
    content = "Line 1\nLine 2\nLine 3"
    response = AgentResponse(content=content)
    assert response.text() == content


# ─── AgentResponse.json() ─────────────────────────────────────────────────────


def test_json_parses_content_as_json():
    response = AgentResponse(content='{"key": "value", "number": 42}')
    parsed = response.json()
    assert parsed == {"key": "value", "number": 42}


def test_json_parses_list_content():
    response = AgentResponse(content='[1, 2, 3]')
    assert response.json() == [1, 2, 3]


def test_json_parses_nested_object():
    response = AgentResponse(content='{"nested": {"a": 1}}')
    assert response.json()["nested"]["a"] == 1


def test_json_raises_on_invalid_content():
    response = AgentResponse(content="not valid json")
    with pytest.raises(Exception):  # json.JSONDecodeError
        response.json()


def test_json_raises_on_empty_content():
    response = AgentResponse(content="")
    with pytest.raises(Exception):
        response.json()


# ─── AgentResponse.__str__() ──────────────────────────────────────────────────


def test_str_returns_content():
    response = AgentResponse(content="My response text")
    assert str(response) == "My response text"


def test_str_returns_empty_string_when_no_content():
    response = AgentResponse()
    assert str(response) == ""


def test_str_works_in_f_string():
    response = AgentResponse(content="hello")
    assert f"Result: {response}" == "Result: hello"


# ─── AgentResponse.__bool__() ─────────────────────────────────────────────────


def test_bool_is_true_when_content_non_empty():
    response = AgentResponse(content="some text")
    assert bool(response) is True


def test_bool_is_false_when_content_empty():
    response = AgentResponse(content="")
    assert bool(response) is False


def test_bool_is_false_when_content_not_set():
    response = AgentResponse()
    assert bool(response) is False


def test_bool_is_true_with_whitespace_content():
    """A response with only whitespace still evaluates as truthy (non-empty string)."""
    response = AgentResponse(content="   ")
    assert bool(response) is True


def test_bool_usable_in_conditional():
    response = AgentResponse(content="text")
    assert response  # truthy

    empty = AgentResponse(content="")
    assert not empty  # falsy


# ─── AgentResponse dataclass fields ───────────────────────────────────────────


def test_tool_calls_default_to_empty_list():
    response = AgentResponse()
    assert response.tool_calls == []


def test_usage_defaults_to_empty_dict():
    response = AgentResponse()
    assert response.usage == {}


def test_raw_defaults_to_none():
    response = AgentResponse()
    assert response.raw is None


def test_all_fields_can_be_set():
    raw_obj = object()
    response = AgentResponse(
        content="text",
        tool_calls=[{"name": "search", "input": {"q": "test"}}],
        usage={"input": 10, "output": 20},
        raw=raw_obj,
    )
    assert response.content == "text"
    assert response.tool_calls == [{"name": "search", "input": {"q": "test"}}]
    assert response.usage == {"input": 10, "output": 20}
    assert response.raw is raw_obj
