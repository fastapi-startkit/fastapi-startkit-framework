"""Tests for Agent.record() — VCR-style record-then-replay."""

import json
import os
import tempfile

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


class SimpleAgent(Agent):
    """Bare-minimum agent for testing — never touches a real API."""

    pass


def test_record_replays_from_existing_file_without_calling_run():
    fixture = {"content": "recorded reply", "tool_calls": [], "usage": {"input": 1, "output": 2}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(fixture, f)
        path = f.name

    try:
        agent = SimpleAgent()
        agent.record(path)

        called = []
        agent._run = lambda *a, **kw: called.append(True)  # type: ignore[method-assign]

        result = agent.prompt("anything")

        assert result.content == "recorded reply"
        assert result.usage == {"input": 1, "output": 2}
        assert called == [], "_run() must not run when a recording already exists"
    finally:
        os.unlink(path)


def test_record_calls_run_and_saves_when_file_missing(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "nested", "cassette.json")

        agent = SimpleAgent()
        agent.record(path)
        monkeypatch.setattr(agent, "_run", lambda *a, **kw: AgentResponse(content="live"))

        result = agent.prompt("hello")

        assert result.content == "live"
        assert os.path.exists(path), "recording should be written on first run"
        with open(path) as f:
            assert json.load(f)["content"] == "live"


def test_record_returns_agent_for_chaining():
    agent = SimpleAgent()
    assert agent.record("ignored.json") is agent


def test_record_respects_custom_pattern():
    agent = SimpleAgent()
    agent.record("never-written.json", pattern="*weather*")

    # Non-matching prompt falls through to _run (no provider configured) → raises.
    import pytest

    with pytest.raises(Exception):
        agent.prompt("tell me a joke")


def test_record_then_replay_roundtrip(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "roundtrip.json")
        calls = []

        agent = SimpleAgent()
        agent.record(path)
        monkeypatch.setattr(
            agent,
            "_run",
            lambda *a, **kw: calls.append(True) or AgentResponse(content="first call"),
        )

        first = agent.prompt("question")
        assert first.content == "first call"
        assert len(calls) == 1

        # A fresh agent pointed at the same cassette replays without calling _run again.
        replay = SimpleAgent()
        replay.record(path)
        replay._run = lambda *a, **kw: calls.append(True)  # type: ignore[method-assign]

        second = replay.prompt("question")
        assert second.content == "first call"
        assert len(calls) == 1, "replay must not call the provider again"
