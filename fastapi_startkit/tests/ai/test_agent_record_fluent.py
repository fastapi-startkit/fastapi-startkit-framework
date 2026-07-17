"""Tests for the fluent Agent.record() testing DSL.

``with Agent.record(cassette) as agent:`` binds a ``RecordingAgent`` handle
with a synchronous ``prompt()`` and assertion methods that judge the most
recent turn — mirroring how a browser-testing ``page`` object exposes
assertions against current page state:

    with RouterAgent.record("cassette.json") as agent:
        agent.prompt("hello")
        agent.assert_text_response()
        agent.assert_tool_not_called(["job_search_tool"])
        agent.assert_response_time_lt(5)

        agent.prompt("suggest python developer jobs")
        agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")
"""

import os
import tempfile
import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage, HumanMessage

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse
from fastapi_startkit.ai.testing import RecordingAgent


class SimpleAgent(Agent):
    pass


def _tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> dict:
    return {"name": name, "args": args or {}, "id": call_id}


class TestFluentPromptMechanics(unittest.TestCase):
    def setup_agent(self, responses: list):
        """responses: list of (content, tool_calls) tuples, consumed in call order."""
        queue = list(responses)

        async def fake_run(agent_self, message, **kwargs):
            content, tool_calls = queue.pop(0)
            return AgentResponse(content=content, tool_calls=tool_calls or [])

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_prompt_is_synchronous_and_returns_agent_response(self):
        self.setup_agent([("Hello there!", [])])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                response = agent.prompt("hi")

        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "Hello there!")

    def test_second_prompt_continues_the_same_session(self):
        self.setup_agent([("Hi!", []), ("here are some jobs", [_tool_call("job_search_tool")])])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hello")
                agent.assert_text_response()

                agent.prompt("suggest python developer jobs")
                agent.assert_tool_called("job_search_tool")

    def test_replaying_from_cassette_preserves_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            self.setup_agent([("", [_tool_call("job_search_tool", {"q": "python"})])])
            with SimpleAgent.record(cassette) as agent:
                agent.prompt("find jobs")

            # No queued responses left — this must replay from cassette, not call _run again.
            with SimpleAgent.record(cassette) as agent:
                agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool")


class TestAssertTextResponse(unittest.TestCase):
    def setup_agent(self, content, tool_calls=None):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content=content, tool_calls=tool_calls or [])

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_when_content_present(self):
        self.setup_agent("Hi!")
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                agent.assert_text_response()

    def test_fails_on_empty_content(self):
        self.setup_agent("", tool_calls=[_tool_call("search")])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_text_response()

    def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    agent.assert_text_response()


class TestAssertToolCalled(unittest.TestCase):
    def setup_agent(self, tool_calls):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="", tool_calls=tool_calls)

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_when_tool_present(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool")

    def test_fails_when_tool_absent(self):
        self.setup_agent([])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_called("job_search_tool")

    def test_predicate_can_accept_via_attribute_access(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")

    def test_predicate_can_reject(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("find jobs")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_called("job_search_tool", lambda tool: tool.args.get("q") == "java")


class TestAssertToolNotCalled(unittest.TestCase):
    def setup_agent(self, tool_calls):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="Hello!", tool_calls=tool_calls)

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_when_absent(self):
        self.setup_agent([])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                agent.assert_tool_not_called(["job_search_tool"])

    def test_fails_when_present(self):
        self.setup_agent([_tool_call("job_search_tool")])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("find jobs")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_not_called(["job_search_tool"])


class TestAssertResponseTimeLt(unittest.TestCase):
    def setup_agent(self):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="Hello!")

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_for_a_fast_call(self):
        self.setup_agent()
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                agent.assert_response_time_lt(5)

    def test_fails_when_exceeded(self):
        self.setup_agent()
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(0)

    def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(5)


class TestRecordMessagesSeed(unittest.TestCase):
    def test_seed_messages_are_included_when_building_the_real_agents_messages(self):
        seed = [HumanMessage(content="Hi"), AIMessage(content="Hello, how can I help?")]
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json"), messages=seed) as agent:
                built = agent._real._build_messages("suggest python developer jobs")

        self.assertEqual(built[0], seed[0])
        self.assertEqual(built[1], seed[1])
        self.assertEqual(built[-1], {"role": "user", "content": "suggest python developer jobs"})

    def test_same_followup_text_with_different_seed_history_does_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "shared.json")

            async def run_a(agent_self, message, **kwargs):
                return AgentResponse(content="job list A")

            with mock.patch.object(SimpleAgent, "_run", run_a):
                with SimpleAgent.record(cassette) as agent:
                    response_a = agent.prompt("suggest python developer jobs")

            async def run_b(agent_self, message, **kwargs):
                return AgentResponse(content="job list B")

            seed = [HumanMessage(content="Hi"), AIMessage(content="Hello, how can I help?")]
            with mock.patch.object(SimpleAgent, "_run", run_b):
                with SimpleAgent.record(cassette, messages=seed) as agent:
                    response_b = agent.prompt("suggest python developer jobs")

        self.assertEqual(response_a.content, "job list A")
        self.assertEqual(response_b.content, "job list B")


class TestAssertResponseJudged(unittest.TestCase):
    def setup_agent(self, content):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content=content)

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_passes_when_judge_approves(self):
        self.setup_agent("Hello there, welcome!")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                RecordingAgent, "_judge_live", return_value={"passed": True, "reasoning": "greets the user"}
            ):
                with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                    agent.prompt("hello")
                    agent.assert_response_judged(
                        model="gpt-3.5-turbo", expectation="The llm should respond with greetings"
                    )

    def test_fails_when_judge_rejects(self):
        self.setup_agent("Completely unrelated content")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                RecordingAgent, "_judge_live", return_value={"passed": False, "reasoning": "not a greeting"}
            ):
                with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                    agent.prompt("hello")
                    with self.assertRaises(AssertionError):
                        agent.assert_response_judged(
                            model="gpt-3.5-turbo", expectation="The llm should respond with greetings"
                        )

    def test_verdict_is_cached_in_the_cassette_and_not_re_judged(self):
        self.setup_agent("Hello there!")
        judge = mock.Mock(return_value={"passed": True, "reasoning": "ok"})
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(RecordingAgent, "_judge_live", judge):
                with SimpleAgent.record(cassette) as agent:
                    agent.prompt("hello")
                    agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")
                    agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

        judge.assert_called_once()

    def test_verdict_persists_to_disk_for_a_later_replay(self):
        self.setup_agent("Hello there!")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(RecordingAgent, "_judge_live", return_value={"passed": True, "reasoning": "ok"}):
                with SimpleAgent.record(cassette) as agent:
                    agent.prompt("hello")
                    agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

            judge = mock.Mock(side_effect=AssertionError("must not be called on replay"))
            with mock.patch.object(RecordingAgent, "_judge_live", judge):
                with SimpleAgent.record(cassette) as agent:
                    agent.prompt("hello")
                    agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

            judge.assert_not_called()

    def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")


class TestJudgeLiveModelCall(unittest.TestCase):
    def test_calls_init_chat_model_and_parses_json_verdict(self):
        captured = {}

        class FakeResult:
            content = '{"passed": true, "reasoning": "Greets the user politely."}'

        class FakeModel:
            def invoke(self, prompt):
                captured["prompt"] = prompt
                return FakeResult()

        patcher = mock.patch.object(chat_models, "init_chat_model", lambda *a, **k: FakeModel())
        patcher.start()
        self.addCleanup(patcher.stop)

        agent = RecordingAgent(SimpleAgent())
        verdict = agent._judge_live("gpt-3.5-turbo", "The llm should respond with greetings", "Hello there!")

        self.assertTrue(verdict["passed"])
        self.assertIn("Greets", verdict["reasoning"])
        self.assertIn("Hello there!", captured["prompt"])


class TestExistingRecordApiIsUnaffected(unittest.IsolatedAsyncioTestCase):
    """The pre-existing bare-context-manager Agent.record() usage (task #327)
    must keep working unchanged alongside the new fluent handle."""

    async def test_bare_context_manager_prompt_still_works(self):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="recorded reply")

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(SimpleAgent, "_run", fake_run):
                with SimpleAgent.record(cassette):
                    result = await SimpleAgent().prompt("hello")

        self.assertEqual(result.content, "recorded reply")
