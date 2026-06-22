"""Tests for the LangChain test harness — fake AIMessage fakes and fake_chat_model.

These exercise a real LangChain agent loop entirely offline. They are skipped
automatically when the optional ``langchain`` extra is not installed.
"""

import pytest

pytest.importorskip("langchain")
pytest.importorskip("langchain_core")

from langchain.agents import create_agent  # noqa: E402
from langchain_core.messages import AIMessage, ToolCall  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from fastapi_startkit.ai import fake_chat_model  # noqa: E402
from fastapi_startkit.ai.agent import Agent  # noqa: E402


class SimpleAgent(Agent):
    pass


@tool
def search_jobs(query: str):
    """Search for jobs matching the query."""
    mock_db = [
        {"title": "Python Developer", "company": "Shopify"},
        {"title": "Data Engineer", "company": "Google"},
    ]
    return [job for job in mock_db if query.lower() in job["title"].lower()] or mock_db


# ─── fake() accepts AIMessage values ─────────────────────────────────────────


def test_fake_with_aimessage_value_returns_content():
    agent = SimpleAgent()
    agent.fake({"*hi*": AIMessage(content="hello there")})

    result = agent.prompt("hi friend")
    assert result.content == "hello there"
    agent.assert_prompted(times=1)


def test_fake_with_aimessage_preserves_tool_calls():
    agent = SimpleAgent()
    call = ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")
    agent.fake({"*job*": AIMessage(content="", tool_calls=[call])})

    result = agent.prompt("find me a job")
    assert result.content == ""
    assert result.tool_calls and result.tool_calls[0]["name"] == "search_jobs"


def test_fake_aimessage_does_not_call_run():
    agent = SimpleAgent()
    agent.fake({"*": AIMessage(content="faked")})

    called = []
    agent._run = lambda *a, **kw: called.append(True)  # type: ignore[method-assign]

    agent.prompt("anything")
    assert called == []


# ─── fake_chat_model drives a full create_agent loop offline ──────────────────


def test_fake_chat_model_runs_tool_calling_agent_offline():
    model = fake_chat_model(
        [
            AIMessage(
                content="",
                tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call")],
            ),
            AIMessage(content="Here is a Python Developer role at Shopify."),
        ]
    )
    agent = create_agent(model=model, tools=[search_jobs])

    result = agent.invoke({"messages": [{"role": "user", "content": "Find me a python job"}]})
    messages = result["messages"]

    assert messages[-1].content == "Here is a Python Developer role at Shopify."
    assert any(getattr(m, "type", None) == "tool" for m in messages), "the tool should have run"


def test_fake_chat_model_accepts_plain_strings():
    model = fake_chat_model(["just a string answer"])
    result = model.invoke("hello")
    assert result.content == "just a string answer"


def test_agent_fake_model_staticmethod_builds_usable_model():
    model = Agent.fake_model([AIMessage(content="from staticmethod")])
    assert model.invoke("hi").content == "from staticmethod"
