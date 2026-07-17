"""Tests for Agent.fake() / Agent.record() and the assert_prompted/reset helpers.

``Agent.fake(responses)`` swaps the agent's *model* for a fake that replays the
given responses in order — the agent itself is untouched, so its real pipeline
(instructions, middleware, schema) still runs. ``Agent.record(cassette)`` swaps in
a record-and-replay model: on a cassette miss it calls the real model once and
caches the response to disk; on a hit it replays without calling the model again.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import langchain.chat_models as chat_models
from langchain_core.messages import AIMessage

from fastapi_startkit.ai import AIConfig, fake_chat_model
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.response import AgentResponse
from fastapi_startkit.application import app


class SimpleAgent(Agent):
    pass


class TestAgentFake(unittest.IsolatedAsyncioTestCase):
    async def test_fake_returns_the_response(self):
        agent = SimpleAgent()
        with SimpleAgent.fake([AIMessage(content="Hello world!")]):
            result = await agent.prompt("anything")

        self.assertIsInstance(result, AgentResponse)
        self.assertEqual(result.content, "Hello world!")

    async def test_fake_accepts_plain_strings(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["matched hello"]):
            result = await agent.prompt("hello")

        self.assertEqual(result.content, "matched hello")

    async def test_fake_replays_responses_in_order(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["first", "second"]):
            first = await agent.prompt("one")
            second = await agent.prompt("two")

        self.assertEqual(first.content, "first")
        self.assertEqual(second.content, "second")

    async def test_fake_does_not_build_the_real_model(self):
        def boom(*_a, **_k):
            raise AssertionError("the real model must not be built when faked")

        with mock.patch.object(chat_models, "init_chat_model", boom):
            with SimpleAgent.fake(["faked"]):
                result = await SimpleAgent().prompt("hello")

        self.assertEqual(result.content, "faked")

    async def test_assert_prompted_passes_after_one_call(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["ok"]):
            await agent.prompt("first")
            agent.assert_prompted()

    async def test_assert_prompted_times_2_passes_after_exactly_2_calls(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["a", "b"]):
            await agent.prompt("first")
            await agent.prompt("second")
            agent.assert_prompted(times=2)

    async def test_assert_prompted_times_fails_when_count_mismatch(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["ok"]):
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
        with SimpleAgent.fake(["ok"]):
            await agent.prompt("a prompt")

            with self.assertRaises(AssertionError):
                agent.assert_not_prompted()

    async def test_reset_clears_call_log(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["ok"]):
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
        with SimpleAgent.fake(["ok"]):
            await agent.prompt("call before reset")

        agent.reset()
        agent.assert_not_prompted()

    async def test_fake_is_scoped_to_the_with_block(self):
        def boom(*_a, **_k):
            raise AssertionError("model should only be faked inside the with block")

        agent = SimpleAgent()
        with SimpleAgent.fake(["first fake"]):
            self.assertEqual((await agent.prompt("call")).content, "first fake")

        with SimpleAgent.fake(["second fake"]):
            self.assertEqual((await agent.prompt("call again")).content, "second fake")

    async def test_fake_as_decorator(self):
        @SimpleAgent.fake(["decorated"])
        async def run():
            return await SimpleAgent().prompt("hi")

        result = await run()
        self.assertEqual(result.content, "decorated")

    async def test_stream_returns_fake_response_in_word_chunks(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["Faked stream!"]):
            chunks = [chunk async for chunk in agent.stream("hello world")]

        self.assertEqual("".join(chunks), "Faked stream!")
        self.assertGreater(len(chunks), 1)
        agent.assert_prompted(times=1)

    async def test_stream_records_one_call_not_two(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["x"]):
            [chunk async for chunk in agent.stream("once")]

        agent.assert_prompted(times=1)


class TestAgentRecord(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def patch_real(self, contents):
        """Patch the real model so a cassette miss returns the next content and
        counts how many times the real model was built (i.e. cassette misses)."""
        calls = []
        remaining = iter(contents)

        def init(*_a, **_k):
            calls.append(True)
            return fake_chat_model([AIMessage(content=next(remaining))])

        patcher = mock.patch.object(chat_models, "init_chat_model", init)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_first_run_records_response_to_cassette(self):
        calls = self.patch_real(["recorded reply"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                result = await SimpleAgent().prompt("hello")

            self.assertEqual(result.content, "recorded reply")
            self.assertEqual(len(calls), 1)
            self.assertTrue(os.path.exists(cassette))
            with open(cassette) as f:
                self.assertIn("recorded reply", json.load(f).values())

    async def test_second_run_replays_without_calling_the_model(self):
        calls = self.patch_real(["recorded reply"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                await SimpleAgent().prompt("hello")
            with SimpleAgent.record(cassette):
                replayed = await SimpleAgent().prompt("hello")

            self.assertEqual(replayed.content, "recorded reply")
            self.assertEqual(len(calls), 1)  # real model built only on the first run

    async def test_replay_prefers_cassette_over_live_response(self):
        self.patch_real(["from first record", "changed live value"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                await SimpleAgent().prompt("hello")
            with SimpleAgent.record(cassette):
                result = await SimpleAgent().prompt("hello")

            self.assertEqual(result.content, "from first record")

    async def test_distinct_messages_are_recorded_separately(self):
        self.patch_real(["hello reply", "goodbye reply"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette):
                await SimpleAgent().prompt("hello")
                await SimpleAgent().prompt("goodbye")

            with open(cassette) as f:
                self.assertEqual(len(json.load(f)), 2)

    def patch_real_stream(self, chunks):
        calls = []

        def init(*_a, **_k):
            calls.append(True)
            return fake_chat_model([AIMessage(content="".join(chunks))])

        patcher = mock.patch.object(chat_models, "init_chat_model", init)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_stream_records_chunks_then_replays_without_calling_the_model(self):
        calls = self.patch_real_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette):
                recorded = [c async for c in SimpleAgent().stream("hi")]
            with SimpleAgent.record(cassette):
                replayed = [c async for c in SimpleAgent().stream("hi")]

            self.assertEqual("".join(recorded), "Hello!")
            self.assertEqual("".join(replayed), "Hello!")
            self.assertEqual(len(calls), 1)  # real stream invoked only on the first run

    async def test_prompt_reads_a_stream_recorded_cassette_as_joined_content(self):
        self.patch_real_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette):
                [c async for c in SimpleAgent().stream("hi")]
            with SimpleAgent.record(cassette):
                response = await SimpleAgent().prompt("hi")

            self.assertEqual(response.content, "Hello!")
