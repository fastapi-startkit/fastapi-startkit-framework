import json
import os
import tempfile
import unittest
from unittest import mock

from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.response import AgentResponse


class SimpleAgent(Agent):
    pass


class TestAgentFake(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        Ai.reset_fakes()

    async def test_fake_replays_the_only_response(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["Hello world!"]):
            result = await agent.prompt("anything")

        self.assertEqual(result.content, "Hello world!")

    async def test_fake_does_not_call_provider_build(self):
        import langchain.chat_models as chat_models

        def fail_if_called(*args, **kwargs):
            raise AssertionError("init_chat_model must not be called when a fake is registered")

        patcher = mock.patch.object(chat_models, "init_chat_model", fail_if_called)
        patcher.start()
        self.addCleanup(patcher.stop)

        agent = SimpleAgent()
        with SimpleAgent.fake(["faked"]):
            await agent.prompt("hello")

    async def test_fake_replays_responses_in_order(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["first reply", "second reply"]):
            first = await agent.prompt("call one")
            second = await agent.prompt("call two")

        self.assertEqual(first.content, "first reply")
        self.assertEqual(second.content, "second reply")

    async def test_fake_raises_once_responses_are_exhausted(self):
        agent = SimpleAgent()
        with SimpleAgent.fake(["only reply"]):
            await agent.prompt("call one")

            with self.assertRaises(RuntimeError):
                await agent.prompt("call two")

    async def test_fake_unregisters_after_the_block_exits(self):
        with SimpleAgent.fake(["faked"]):
            self.assertTrue(Ai.has_fake_model_for("SimpleAgent"))

        self.assertFalse(Ai.has_fake_model_for("SimpleAgent"))

    async def test_fake_as_decorator(self):
        @SimpleAgent.fake(["decorated reply"])
        async def run():
            return await SimpleAgent().prompt("call")

        result = await run()

        self.assertEqual(result.content, "decorated reply")

    async def test_assert_prompted_passes_after_one_call(self):
        with SimpleAgent.fake(["ok"]) as agent:
            await agent.prompt("first")
            agent.assert_prompted()

    async def test_assert_prompted_times_2_passes_after_exactly_2_calls(self):
        with SimpleAgent.fake(["ok", "ok"]) as agent:
            await agent.prompt("first")
            await agent.prompt("second")
            agent.assert_prompted(times=2)

    async def test_assert_prompted_times_fails_when_count_mismatch(self):
        with SimpleAgent.fake(["ok"]) as agent:
            await agent.prompt("only once")

            with self.assertRaises(AssertionError):
                agent.assert_prompted(times=2)

    def test_assert_prompted_fails_when_never_called(self):
        with SimpleAgent.fake([]) as agent:
            with self.assertRaises(AssertionError):
                agent.assert_prompted()

    def test_assert_prompted_times_zero_passes_when_never_called(self):
        with SimpleAgent.fake([]) as agent:
            agent.assert_prompted(times=0)

    def test_assert_not_prompted_passes_when_no_calls_made(self):
        with SimpleAgent.fake([]) as agent:
            agent.assert_not_prompted()

    async def test_assert_not_prompted_fails_after_one_call(self):
        with SimpleAgent.fake(["ok"]) as agent:
            await agent.prompt("a prompt")

            with self.assertRaises(AssertionError):
                agent.assert_not_prompted()

    async def test_reset_clears_call_log(self):
        with SimpleAgent.fake(["ok"]) as agent:
            await agent.prompt("first")
            self.assertEqual(len(agent._prompts), 1)

            agent.reset()
            self.assertEqual(agent._prompts, [])

    def test_reset_returns_the_handle_for_chaining(self):
        with SimpleAgent.fake([]) as agent:
            self.assertIs(agent.reset(), agent)

    async def test_assert_not_prompted_passes_after_reset(self):
        with SimpleAgent.fake(["ok"]) as agent:
            await agent.prompt("call before reset")
            agent.reset()
            agent.assert_not_prompted()

    async def test_fake_rebinding_overrides_previous(self):
        with SimpleAgent.fake(["first fake"]) as agent:
            self.assertEqual((await agent.prompt("call")).content, "first fake")

        with SimpleAgent.fake(["second fake"]) as agent:
            self.assertEqual((await agent.prompt("call again")).content, "second fake")

    async def test_stream_returns_fake_response(self):
        with SimpleAgent.fake(["Faked stream!"]) as agent:
            chunks = [frame["text"] async for frame in agent.stream("hello world")]

            self.assertEqual("".join(chunks), "Faked stream!")
            self.assertGreater(len(chunks), 1)
            agent.assert_prompted(times=1)

    async def test_stream_replays_the_registered_text_exactly(self):
        with SimpleAgent.fake(["Hello there, friend"]) as agent:
            chunks = [frame["text"] async for frame in agent.stream("hi")]

            self.assertEqual("".join(chunks), "Hello there, friend")

    async def test_stream_records_one_call_not_two(self):
        with SimpleAgent.fake(["x"]) as agent:
            [chunk async for chunk in agent.stream("once")]

            # Streaming must record exactly one call — not one for stream + one for prompt.
            agent.assert_prompted(times=1)


class TestAgentRecord(unittest.IsolatedAsyncioTestCase):
    def setup_agent(self, content):
        calls = []

        async def fake_run(agent_self, message, **kwargs):
            calls.append(message)
            return AgentResponse(content=content)

        patcher = mock.patch.object(SimpleAgent, "prompt", fake_run)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_first_run_records_response_to_cassette(self):
        calls = self.setup_agent("recorded reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette) as agent:
                result = await agent.prompt("hello")

            self.assertEqual(result.content, "recorded reply")
            self.assertEqual(calls, ["hello"])
            self.assertTrue(os.path.exists(cassette))
            with open(cassette) as f:
                store = json.load(f)
            (turn,) = store.values()
            self.assertEqual(turn[0], {"type": "human", "content": "hello"})
            self.assertTrue(
                any(entry.get("type") == "ai" and entry.get("content") == "recorded reply" for entry in turn)
            )

    async def test_second_run_replays_without_calling_run(self):
        calls = self.setup_agent("recorded reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette) as agent:
                await agent.prompt("hello")
            with SimpleAgent.record(cassette) as agent:
                replayed = await agent.prompt("hello")

            self.assertEqual(replayed.content, "recorded reply")
            self.assertEqual(calls, ["hello"])

    async def test_replay_prefers_cassette_over_live_response(self):
        async def first_run(s, m, **k):
            return AgentResponse(content="from first record")

        async def changed_run(s, m, **k):
            return AgentResponse(content="changed live value")

        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with mock.patch.object(SimpleAgent, "prompt", first_run):
                with SimpleAgent.record(cassette) as agent:
                    await agent.prompt("hello")
            with mock.patch.object(SimpleAgent, "prompt", changed_run):
                with SimpleAgent.record(cassette) as agent:
                    result = await agent.prompt("hello")

            self.assertEqual(result.content, "from first record")

    async def test_distinct_messages_are_recorded_separately(self):
        calls = self.setup_agent("reply")
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "c.json")
            with SimpleAgent.record(cassette) as agent:
                await agent.prompt("hello")
                await agent.prompt("goodbye")

            self.assertEqual(calls, ["hello", "goodbye"])
            with open(cassette) as f:
                self.assertEqual(len(json.load(f)), 2)

    def setup_stream(self, chunks):
        from fastapi_startkit.ai.runner import Runner

        calls = []

        async def fake_stream(runner_self, message, **kwargs):
            calls.append(message)
            for chunk in chunks:
                yield {"type": "delta", "text": chunk}

        # The fluent fakes drive the runner's stream() directly (so they can read
        # the structured response it captures), so mock at that layer.
        patcher = mock.patch.object(Runner, "stream", fake_stream)
        patcher.start()
        self.addCleanup(patcher.stop)
        return calls

    async def test_stream_first_run_records_chunk_list_to_cassette(self):
        calls = self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette) as agent:
                chunks = [frame["text"] async for frame in agent.stream("hi")]

            self.assertEqual(chunks, ["Hel", "lo!"])
            self.assertEqual(calls, ["hi"])
            with open(cassette) as f:
                (turn,) = json.load(f).values()
            self.assertEqual(turn[0], {"type": "human", "content": "hi"})
            self.assertEqual(turn[1]["type"], "ai")
            self.assertEqual(turn[1]["content"], "Hello!")
            self.assertEqual(turn[1]["chunks"], ["Hel", "lo!"])

    async def test_stream_second_run_replays_chunks_without_calling_stream(self):
        calls = self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette) as agent:
                [c async for c in agent.stream("hi")]
            with SimpleAgent.record(cassette) as agent:
                replayed = [frame["text"] async for frame in agent.stream("hi")]

            self.assertEqual(replayed, ["Hel", "lo!"])
            self.assertEqual(calls, ["hi"])  # real stream invoked only on the first run

    async def test_prompt_reads_a_stream_recorded_cassette_as_joined_content(self):
        self.setup_stream(["Hel", "lo!"])
        with tempfile.TemporaryDirectory() as tmp:
            cassette = os.path.join(tmp, "s.json")
            with SimpleAgent.record(cassette) as agent:
                [c async for c in agent.stream("hi")]
            with SimpleAgent.record(cassette) as agent:
                response = await agent.prompt("hi")

            self.assertEqual(response.content, "Hello!")
