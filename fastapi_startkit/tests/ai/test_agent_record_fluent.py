"""Tests for the fluent Agent.record() testing DSL.

``with Agent.record(cassette) as agent:`` binds an ``AgentRecordFake`` handle
whose async ``prompt()`` and assertion methods judge the most recent turn —
mirroring how a browser-testing ``page`` object exposes assertions against
current page state:

    with RouterAgent.record("cassette.json") as agent:
        await agent.prompt("hello")
        agent.assert_text_response()
        agent.assert_tool_not_called(["job_search_tool"])
        agent.assert_response_time_lt(5)

        await agent.prompt("suggest python developer jobs")
        agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")
"""

import os
import tempfile
import unittest
from unittest import mock

from langchain_core.messages import AIMessage, HumanMessage

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.runner import Runner
from fastapi_startkit.ai.response import AgentResponse
from fastapi_startkit.ai.testing import AgentRecordFake


class SimpleAgent(Agent):
    pass


def _tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> dict:
    return {"name": name, "args": args or {}, "id": call_id}


class TestFluentPromptMechanics(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, responses: list):
        """responses: list of (content, tool_calls) tuples, consumed in call order."""
        queue = list(responses)

        async def fake_run(agent_self, message, **kwargs):
            content, tool_calls = queue.pop(0)
            return AgentResponse(content=content, tool_calls=tool_calls or [])

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_prompt_is_async_and_returns_agent_response(self):
        self.setup_agent([("Hello there!", [])])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                response = await agent.prompt("hi")

        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "Hello there!")

    async def test_second_prompt_continues_the_same_session(self):
        self.setup_agent([("Hi!", []), ("here are some jobs", [_tool_call("job_search_tool")])])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hello")
                agent.assert_text_response()

                await agent.prompt("suggest python developer jobs")
                agent.assert_tool_called("job_search_tool")

    async def test_replaying_from_cassette_preserves_tool_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            self.setup_agent([("", [_tool_call("job_search_tool", {"q": "python"})])])
            with SimpleAgent.record(cassette) as agent:
                await agent.prompt("find jobs")

            # No queued responses left — this must replay from cassette, not call _run again.
            with SimpleAgent.record(cassette) as agent:
                await agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool")


class TestAssertTextResponse(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, content, tool_calls=None):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content=content, tool_calls=tool_calls or [])

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_passes_when_content_present(self):
        self.setup_agent("Hi!")
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                agent.assert_text_response()

    async def test_fails_on_empty_content(self):
        self.setup_agent("", tool_calls=[_tool_call("search")])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_text_response()

    async def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    agent.assert_text_response()


class TestAssertToolCalled(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, tool_calls):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="", tool_calls=tool_calls)

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_passes_when_tool_present(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool")

    async def test_fails_when_tool_absent(self):
        self.setup_agent([])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_called("job_search_tool")

    async def test_predicate_can_accept_via_attribute_access(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("find jobs")
                agent.assert_tool_called("job_search_tool", lambda tool: tool.name == "job_search_tool")

    async def test_predicate_can_reject(self):
        self.setup_agent([_tool_call("job_search_tool", {"q": "python"})])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("find jobs")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_called("job_search_tool", lambda tool: tool.args.get("q") == "java")


class TestAssertToolNotCalled(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, tool_calls):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="Hello!", tool_calls=tool_calls)

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_passes_when_absent(self):
        self.setup_agent([])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                agent.assert_tool_not_called(["job_search_tool"])

    async def test_fails_when_present(self):
        self.setup_agent([_tool_call("job_search_tool")])
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("find jobs")
                with self.assertRaises(AssertionError):
                    agent.assert_tool_not_called(["job_search_tool"])


class TestAssertResponseTimeLt(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="Hello!")

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_passes_for_a_fast_call(self):
        self.setup_agent()
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                agent.assert_response_time_lt(5)

    async def test_fails_when_exceeded(self):
        self.setup_agent()
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                await agent.prompt("hi")
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(0)

    async def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    agent.assert_response_time_lt(5)


class TestRecordMessagesSeed(unittest.IsolatedAsyncioTestCase):
    async def test_seed_messages_are_included_when_building_the_real_agents_messages(self):
        seed = [HumanMessage(content="Hi"), AIMessage(content="Hello, how can I help?")]
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json"), messages=seed) as agent:
                built = Runner(agent._real)._build_messages("suggest python developer jobs")

        self.assertEqual(built[0], seed[0])
        self.assertEqual(built[1], seed[1])
        self.assertEqual(built[-1], {"role": "user", "content": "suggest python developer jobs"})

    async def test_same_followup_text_with_different_seed_history_does_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "shared.json")

            async def run_a(agent_self, message, **kwargs):
                return AgentResponse(content="job list A")

            with mock.patch.object(SimpleAgent, "prompt", run_a):
                with SimpleAgent.record(cassette) as agent:
                    response_a = await agent.prompt("suggest python developer jobs")

            async def run_b(agent_self, message, **kwargs):
                return AgentResponse(content="job list B")

            seed = [HumanMessage(content="Hi"), AIMessage(content="Hello, how can I help?")]
            with mock.patch.object(SimpleAgent, "prompt", run_b):
                with SimpleAgent.record(cassette, messages=seed) as agent:
                    response_b = await agent.prompt("suggest python developer jobs")

        self.assertEqual(response_a.content, "job list A")
        self.assertEqual(response_b.content, "job list B")


class TestAssertResponseJudged(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, content):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content=content)

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_passes_when_judge_approves(self):
        self.setup_agent("Hello there, welcome!")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                AgentRecordFake,
                "_judge_live",
                mock.AsyncMock(return_value={"passed": True, "reasoning": "greets the user"}),
            ):
                with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("hello")
                    await agent.assert_response_judged(
                        model="gpt-3.5-turbo", expectation="The llm should respond with greetings"
                    )

    async def test_fails_when_judge_rejects(self):
        self.setup_agent("Completely unrelated content")
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(
                AgentRecordFake,
                "_judge_live",
                mock.AsyncMock(return_value={"passed": False, "reasoning": "not a greeting"}),
            ):
                with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("hello")
                    with self.assertRaises(AssertionError):
                        await agent.assert_response_judged(
                            model="gpt-3.5-turbo", expectation="The llm should respond with greetings"
                        )

    async def test_verdict_is_cached_in_the_cassette_and_not_re_judged(self):
        self.setup_agent("Hello there!")
        judge = mock.AsyncMock(return_value={"passed": True, "reasoning": "ok"})
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with SimpleAgent.record(cassette) as agent:
                    await agent.prompt("hello")
                    await agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")
                    await agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

        judge.assert_called_once()

    async def test_verdict_persists_to_disk_for_a_later_replay(self):
        self.setup_agent("Hello there!")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(
                AgentRecordFake, "_judge_live", mock.AsyncMock(return_value={"passed": True, "reasoning": "ok"})
            ):
                with SimpleAgent.record(cassette) as agent:
                    await agent.prompt("hello")
                    await agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

            judge = mock.AsyncMock(side_effect=AssertionError("must not be called on replay"))
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with SimpleAgent.record(cassette) as agent:
                    await agent.prompt("hello")
                    await agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

            judge.assert_not_called()

    async def test_fails_when_no_prompt_has_been_made(self):
        with tempfile.TemporaryDirectory() as tmp:
            with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                with self.assertRaises(AssertionError):
                    await agent.assert_response_judged(model="gpt-3.5-turbo", expectation="greet")

    async def test_provider_is_forwarded_to_the_judge(self):
        self.setup_agent("Hello there!")
        judge = mock.AsyncMock(return_value={"passed": True, "reasoning": "ok"})
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(AgentRecordFake, "_judge_live", judge):
                with SimpleAgent.record(os.path.join(tmp, "c.json")) as agent:
                    await agent.prompt("hello")
                    await agent.assert_response_judged(model="gpt-3.5-turbo", provider="openai", expectation="greet")

        judge.assert_called_once_with("gpt-3.5-turbo", "greet", "Hello there!", "openai")


class TestExistingRecordApiIsUnaffected(unittest.IsolatedAsyncioTestCase):
    """The pre-existing bare-context-manager Agent.record() usage (task #327)
    must keep working unchanged alongside the new fluent handle."""

    async def test_bare_context_manager_prompt_still_works(self):
        async def fake_run(agent_self, message, **kwargs):
            return AgentResponse(content="recorded reply")

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(SimpleAgent, "prompt", fake_run):
                with SimpleAgent.record(cassette) as agent:
                    result = await agent.prompt("hello")

        self.assertEqual(result.content, "recorded reply")
