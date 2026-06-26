"""Tests for Agent.fake() / Agent.record() and the assert_prompted/reset helpers.

``Agent.fake()`` binds a canned stand-in into the container for the duration of a
``with`` block. ``Agent.record()`` binds a record-and-replay stand-in: on a cassette
miss it calls the real agent once and caches the response to disk; on a hit it
replays from the cassette without calling the agent again.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse


class SimpleAgent(Agent):
    pass


class TestAgentFake(unittest.IsolatedAsyncioTestCase):
    async def test_fake_with_agent_response_returns_it(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="Hello world!")}):
            result = await agent.prompt("anything")

        self.assertEqual(result.content, "Hello world!")

    async def test_fake_does_not_call_provider_run(self):
        agent = SimpleAgent()
        called = []

        original_run = agent._run

        async def patched_run(*args, **kwargs):
            called.append(True)
            return await original_run(*args, **kwargs)

        agent._run = patched_run

        with SimpleAgent.fake({"*": AgentResponse(content="faked")}):
            await agent.prompt("hello")

        self.assertEqual(called, [], "_run() must not be called when a fake matches")

    async def test_fake_with_exact_pattern(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"hello": AgentResponse(content="matched hello")}):
            result = await agent.prompt("hello")

        self.assertEqual(result.content, "matched hello")

    async def test_fake_glob_hello_wildcard(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*hello*": AgentResponse(content="hi there")}):
            result = await agent.prompt("say hello to me")

        self.assertEqual(result.content, "hi there")

    async def test_fake_glob_analyze_wildcard(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*analyze*": AgentResponse(content="analysis done")}):
            result = await agent.prompt("please analyze this report")

        self.assertEqual(result.content, "analysis done")

    async def test_fake_no_match_raises(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*hello*": AgentResponse(content="hi")}):
            with self.assertRaises(Exception):
                await agent.prompt("goodbye")

    async def test_fake_glob_case_insensitive(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*HELLO*": AgentResponse(content="case insensitive")}):
            result = await agent.prompt("say hello please")

        self.assertEqual(result.content, "case insensitive")

    async def test_fake_first_matching_pattern_wins(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(
            {
                "*hello*": AgentResponse(content="first match"),
                "*hello world*": AgentResponse(content="second match"),
            }
        ):
            result = await agent.prompt("hello world")

        self.assertEqual(result.content, "first match")

    async def test_assert_prompted_passes_after_one_call(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("first")
            agent.assert_prompted()

    async def test_assert_prompted_times_2_passes_after_exactly_2_calls(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("first")
            await agent.prompt("second")
            agent.assert_prompted(times=2)

    async def test_assert_prompted_times_fails_when_count_mismatch(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("only once")

            with self.assertRaises(AssertionError):
                agent.assert_prompted(times=2)

    def test_assert_prompted_fails_when_never_called(self):
        agent = SimpleAgent()

        with self.assertRaises(AssertionError):
            agent.assert_prompted()

    def test_assert_prompted_times_zero_passes_when_never_called(self):
        agent = SimpleAgent()
        agent.assert_prompted(times=0)

    def test_assert_not_prompted_passes_when_no_calls_made(self):
        agent = SimpleAgent()
        agent.assert_not_prompted()

    async def test_assert_not_prompted_fails_after_one_call(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("a prompt")

            with self.assertRaises(AssertionError):
                agent.assert_not_prompted()

    async def test_reset_clears_call_log(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("first")
            self.assertEqual(len(agent._call_log), 1)

        agent.reset()
        self.assertEqual(agent._call_log, [])

    def test_reset_returns_agent_for_chaining(self):
        agent = SimpleAgent()
        result = agent.reset()
        self.assertIs(result, agent)

    async def test_assert_not_prompted_passes_after_reset(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="ok")}):
            await agent.prompt("call before reset")

        agent.reset()
        agent.assert_not_prompted()

    async def test_fake_rebinding_overrides_previous(self):
        agent = SimpleAgent()

        with SimpleAgent.fake({"*": AgentResponse(content="first fake")}):
            self.assertEqual((await agent.prompt("call")).content, "first fake")

        with SimpleAgent.fake({"*": AgentResponse(content="second fake")}):
            self.assertEqual((await agent.prompt("call again")).content, "second fake")

    async def test_stream_returns_fake_response(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*hello*": AgentResponse(content="Faked stream!")}):
            chunks = [chunk async for chunk in agent.stream("hello world")]

        self.assertEqual(chunks, ["Faked stream!"])
        agent.assert_prompted(times=1)

    async def test_stream_records_one_call_not_two(self):
        agent = SimpleAgent()
        with SimpleAgent.fake({"*": AgentResponse(content="x")}):
            [chunk async for chunk in agent.stream("once")]

        # Streaming must log exactly one prompt — not one for stream + one for prompt.
        agent.assert_prompted(times=1)


class TestAgentRecord(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, content):
        calls = []

        async def fake_run(agent_self, message, **kwargs):
            calls.append(message)
            return AgentResponse(content=content)

        patcher = mock.patch.object(SimpleAgent, "_run", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_first_run_records_response_to_cassette(self):
        calls = self.setup_agent("recorded reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                result = await SimpleAgent().prompt("hello")

            self.assertEqual(result.content, "recorded reply")
            self.assertEqual(calls, ["hello"])
            self.assertTrue(os.path.exists(cassette))
            with open(cassette) as f:
                self.assertIn("recorded reply", json.load(f).values())

    async def test_second_run_replays_without_calling_run(self):
        calls = self.setup_agent("recorded reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                await SimpleAgent().prompt("hello")
            with SimpleAgent.record(cassette):
                replayed = await SimpleAgent().prompt("hello")

            self.assertEqual(replayed.content, "recorded reply")
            self.assertEqual(calls, ["hello"])

    async def test_replay_prefers_cassette_over_live_response(self):
        async def first_run(s, m, **k):
            return AgentResponse(content="from first record")

        async def changed_run(s, m, **k):
            return AgentResponse(content="changed live value")

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(SimpleAgent, "_run", first_run):
                with SimpleAgent.record(cassette):
                    await SimpleAgent().prompt("hello")
            with mock.patch.object(SimpleAgent, "_run", changed_run):
                with SimpleAgent.record(cassette):
                    result = await SimpleAgent().prompt("hello")

            self.assertEqual(result.content, "from first record")

    async def test_distinct_messages_are_recorded_separately(self):
        calls = self.setup_agent("reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                await SimpleAgent().prompt("hello")
                await SimpleAgent().prompt("goodbye")

            self.assertEqual(calls, ["hello", "goodbye"])
            with open(cassette) as f:
                self.assertEqual(len(json.load(f)), 2)

    def setup_stream(self, chunks):
        calls = []

        async def fake_stream(agent_self, message, **kwargs):
            calls.append(message)
            for chunk in chunks:
                yield chunk

        patcher = mock.patch.object(SimpleAgent, "_stream", fake_stream)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_stream_first_run_records_chunk_list_to_cassette(self):
        calls = self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette):
                chunks = [c async for c in SimpleAgent().stream("hi")]

            self.assertEqual(chunks, ["Hel", "lo!"])
            self.assertEqual(calls, ["hi"])
            with open(cassette) as f:
                self.assertEqual(list(json.load(f).values()), [["Hel", "lo!"]])

    async def test_stream_second_run_replays_chunks_without_calling_stream(self):
        calls = self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette):
                [c async for c in SimpleAgent().stream("hi")]
            with SimpleAgent.record(cassette):
                replayed = [c async for c in SimpleAgent().stream("hi")]

            self.assertEqual(replayed, ["Hel", "lo!"])
            self.assertEqual(calls, ["hi"])  # real stream invoked only on the first run

    async def test_prompt_reads_a_stream_recorded_cassette_as_joined_content(self):
        self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette):
                [c async for c in SimpleAgent().stream("hi")]
            with SimpleAgent.record(cassette):
                response = await SimpleAgent().prompt("hi")

            self.assertEqual(response.content, "Hello!")
