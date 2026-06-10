"""Tests for Agent.fake(), assert_prompted(), assert_not_prompted(), and reset()."""

import json
import os
import tempfile

import pytest
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse, AgentSnapshot


# ─── Helpers ──────────────────────────────────────────────────────────────────


class SimpleAgent(Agent):
    """Bare-minimum agent for testing — never touches a real API."""

    pass


# ─── fake() with AgentResponse returns it without hitting the API ──────────────


def test_fake_with_agent_response_returns_it():
    agent = SimpleAgent()
    expected = AgentResponse(content="Hello world!")
    agent.fake({"*": expected})

    result = agent.prompt("anything")

    assert result.content == "Hello world!"


def test_fake_does_not_call_provider_run():
    """fake() must short-circuit before _run() is ever invoked."""
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="faked")})

    called = []

    original_run = agent._run

    def patched_run(*args, **kwargs):
        called.append(True)
        return original_run(*args, **kwargs)

    agent._run = patched_run  # type: ignore[method-assign]
    agent.prompt("hello")

    assert called == [], "_run() must not be called when a fake matches"


def test_fake_with_exact_pattern():
    agent = SimpleAgent()
    agent.fake({"hello": AgentResponse(content="matched hello")})

    result = agent.prompt("hello")
    assert result.content == "matched hello"


# ─── fake() with glob pattern matching ────────────────────────────────────────


def test_fake_glob_hello_wildcard():
    agent = SimpleAgent()
    agent.fake({"*hello*": AgentResponse(content="hi there")})

    result = agent.prompt("say hello to me")
    assert result.content == "hi there"


def test_fake_glob_analyze_wildcard():
    agent = SimpleAgent()
    agent.fake({"*analyze*": AgentResponse(content="analysis done")})

    result = agent.prompt("please analyze this report")
    assert result.content == "analysis done"


def test_fake_glob_no_match_raises_on_missing_run():
    """When a pattern does not match and no real provider is configured, _run raises."""
    agent = SimpleAgent()
    agent.fake({"*hello*": AgentResponse(content="hi")})

    with pytest.raises(Exception):
        agent.prompt("goodbye")  # pattern does not match → falls through to _run


def test_fake_glob_case_insensitive():
    agent = SimpleAgent()
    agent.fake({"*HELLO*": AgentResponse(content="case insensitive")})

    result = agent.prompt("say hello please")
    assert result.content == "case insensitive"


def test_fake_first_matching_pattern_wins():
    agent = SimpleAgent()
    agent.fake(
        {
            "*hello*": AgentResponse(content="first match"),
            "*hello world*": AgentResponse(content="second match"),
        }
    )

    result = agent.prompt("hello world")
    assert result.content == "first match"


# ─── fake() with AgentSnapshot loads from fixture if file exists ───────────────


def test_fake_with_snapshot_loads_from_file_if_exists():
    fixture_data = {"content": "snapshot reply", "tool_calls": [], "usage": {"input": 5, "output": 10}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(fixture_data, f)
        fixture_path = f.name

    try:
        agent = SimpleAgent()
        snapshot = AgentSnapshot(path=fixture_path)
        agent.fake({"*": snapshot})

        result = agent.prompt("any prompt")
        assert result.content == "snapshot reply"
        assert result.usage == {"input": 5, "output": 10}
    finally:
        os.unlink(fixture_path)


def test_fake_with_snapshot_missing_file_calls_run(monkeypatch):
    """When the snapshot file does not exist, _run() is called and the result is saved."""
    expected_response = AgentResponse(content="live result")

    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = os.path.join(tmpdir, "snap.json")

        agent = SimpleAgent()
        snapshot = AgentSnapshot(path=snapshot_path)
        agent.fake({"*": snapshot})

        # Patch _run to avoid real API call
        monkeypatch.setattr(agent, "_run", lambda *a, **kw: expected_response)

        result = agent.prompt("test message")
        assert result.content == "live result"

        # Snapshot should now be saved to disk
        assert os.path.exists(snapshot_path)
        with open(snapshot_path) as f:
            saved = json.load(f)
        assert saved["content"] == "live result"


# ─── assert_prompted() ────────────────────────────────────────────────────────


def test_assert_prompted_passes_after_one_call():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("first")
    agent.assert_prompted()  # must not raise


def test_assert_prompted_times_2_passes_after_exactly_2_calls():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("first")
    agent.prompt("second")
    agent.assert_prompted(times=2)  # must not raise


def test_assert_prompted_times_fails_when_count_mismatch():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("only once")

    with pytest.raises(AssertionError):
        agent.assert_prompted(times=2)


def test_assert_prompted_fails_when_never_called():
    agent = SimpleAgent()

    with pytest.raises(AssertionError):
        agent.assert_prompted()


def test_assert_prompted_times_zero_passes_when_never_called():
    agent = SimpleAgent()
    agent.assert_prompted(times=0)  # must not raise


# ─── assert_not_prompted() ────────────────────────────────────────────────────


def test_assert_not_prompted_passes_when_no_calls_made():
    agent = SimpleAgent()
    agent.assert_not_prompted()  # must not raise


def test_assert_not_prompted_fails_after_one_call():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("a prompt")

    with pytest.raises(AssertionError):
        agent.assert_not_prompted()


# ─── reset() ──────────────────────────────────────────────────────────────────


def test_reset_clears_call_log():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("first")
    assert len(agent._call_log) == 1

    agent.reset()
    assert agent._call_log == []


def test_reset_clears_fakes():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})
    assert len(agent._fakes) == 1

    agent.reset()
    assert agent._fakes == {}


def test_reset_returns_agent_for_chaining():
    agent = SimpleAgent()
    result = agent.reset()
    assert result is agent


def test_assert_not_prompted_passes_after_reset():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="ok")})

    agent.prompt("call before reset")
    agent.reset()

    agent.assert_not_prompted()  # call log was cleared


def test_fake_after_reset_works_normally():
    agent = SimpleAgent()
    agent.fake({"*": AgentResponse(content="first fake")})
    agent.prompt("call")
    agent.reset()

    agent.fake({"*": AgentResponse(content="second fake")})
    result = agent.prompt("call again")
    assert result.content == "second fake"


# ─── stream() respects fake() ─────────────────────────────────────────────────


def test_stream_returns_fake_response():
    agent = SimpleAgent()
    agent.fake({"*hello*": AgentResponse(content="Faked stream!")})

    chunks = list(agent.stream("hello world"))

    assert chunks == ["Faked stream!"]
    agent.assert_prompted(times=1)
