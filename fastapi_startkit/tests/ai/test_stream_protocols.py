import json
import re
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, ToolCall, ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.tools import tool

from fastapi_startkit.ai import (
    AgentUserInteractionProtocol,
    AIConfig,
    StreamableAgentResponse,
    StreamProtocol,
    VercelDataProtocol,
)
from fastapi_startkit.ai.agent import Agent
from fastapi_startkit.ai.ai import Ai
from fastapi_startkit.ai.streaming import (
    StepFinished,
    StepStarted,
    StreamFailed,
    StreamFinished,
    StreamStarted,
    TextDelta,
    TextEnded,
    TextStarted,
    ToolInputAvailable,
    ToolInputDelta,
    ToolInputStarted,
    ToolOutputAvailable,
)
from fastapi_startkit.application import app


def event(kind: str, **data: Any) -> dict[str, Any]:
    return {"event": kind, "name": "model", "run_id": "r", "tags": [], "metadata": {}, "parent_ids": [], "data": data}


def chunk(content: Any = "", **kwargs: Any) -> dict[str, Any]:
    return event("on_chat_model_stream", chunk=AIMessageChunk(content=content, **kwargs))


def scripted(*events: dict[str, Any], error: Exception | None = None, closed: list[bool] | None = None):
    async def source() -> AsyncIterator[dict[str, Any]]:
        try:
            for item in events:
                yield item
            if error is not None:
                raise error
        finally:
            if closed is not None:
                closed.append(True)

    stream = StreamableAgentResponse(source)
    stream.invocation_id = "inv"
    return stream


def frames(body: str) -> list[Any]:
    payloads = [line.removeprefix("data: ") for line in body.split("\n\n") if line]
    return [payload if payload == "[DONE]" else json.loads(payload) for payload in payloads]


async def encoded(protocol: StreamProtocol, stream: StreamableAgentResponse) -> list[Any]:
    return frames("".join([frame async for frame in protocol.encode(stream)]))


TEXT_STREAM = (
    event("on_chat_model_start"),
    chunk("Hello"),
    chunk(" world"),
    event("on_chat_model_end", output=AIMessage(content="Hello world")),
)

TOOL_STREAM = (
    event("on_chat_model_start"),
    chunk("Looking"),
    chunk(tool_call_chunks=[{"name": "search", "args": '{"q":', "id": "call_1", "index": 0}]),
    chunk(tool_call_chunks=[{"name": None, "args": '"py"}', "id": None, "index": 0}]),
    event(
        "on_chat_model_end",
        output=AIMessage(content="Looking", tool_calls=[ToolCall(name="search", args={"q": "py"}, id="call_1")]),
    ),
    event("on_tool_start", input={"q": "py"}),
    event("on_tool_end", output=ToolMessage(content='{"jobs": 2}', tool_call_id="call_1", name="search")),
)

REASONING_STREAM = (
    event("on_chat_model_start"),
    chunk([{"type": "thinking", "thinking": "Hmm"}]),
    chunk([{"type": "text", "text": "Done"}]),
)


class TestNormalizer:
    async def test_text_stream_is_bracketed(self):
        events = [e async for e in scripted(*TEXT_STREAM).events()]

        assert events == [
            StreamStarted("inv"),
            StepStarted(),
            TextStarted("inv-text-1"),
            TextDelta("inv-text-1", "Hello"),
            TextDelta("inv-text-1", " world"),
            TextEnded("inv-text-1"),
            StepFinished(),
            StreamFinished(),
        ]

    async def test_tool_call_streams_arguments_then_result(self):
        events = [e async for e in scripted(*TOOL_STREAM).events()]

        assert events[4:] == [
            TextEnded("inv-text-1"),
            ToolInputStarted("call_1", "search"),
            ToolInputDelta("call_1", '{"q":'),
            ToolInputDelta("call_1", '"py"}'),
            ToolInputAvailable("call_1", "search", {"q": "py"}),
            ToolOutputAvailable("call_1", "search", {"jobs": 2}),
            StepFinished(),
            StreamFinished(),
        ]

    async def test_tool_calls_that_never_streamed_are_sent_whole(self):
        stream = scripted(
            event("on_chat_model_start"),
            event(
                "on_chat_model_end",
                output=AIMessage(content="", tool_calls=[ToolCall(name="search", args={"q": "py"}, id="c9")]),
            ),
            event("on_tool_end", output=ToolMessage(content="plain text", tool_call_id="c9", name="search")),
        )

        events = [e async for e in stream.events()]

        assert events[2:6] == [
            ToolInputStarted("c9", "search"),
            ToolInputDelta("c9", '{"q": "py"}'),
            ToolInputAvailable("c9", "search", {"q": "py"}),
            ToolOutputAvailable("c9", "search", "plain text"),
        ]

    async def test_tool_output_without_a_requested_call_uses_the_message_id(self):
        stream = scripted(event("on_tool_end", output=ToolMessage(content="ok", tool_call_id="t1", name="lookup")))

        events = [e async for e in stream.events()]

        assert ToolOutputAvailable("t1", "lookup", "ok") in events

    async def test_reasoning_shapes_are_extracted(self):
        stream = scripted(
            chunk("", additional_kwargs={"reasoning_content": "a"}),
            chunk([{"type": "reasoning", "reasoning": "b"}]),
            chunk([{"type": "reasoning", "summary": [{"type": "summary_text", "text": "c"}]}]),
            chunk([{"type": "reasoning_content", "reasoning_content": {"text": "d"}}]),
            chunk(["e", {"type": "image"}]),
        )

        events = [e async for e in stream.events()]

        reasoning = [e.delta for e in events if type(e).__name__ == "ReasoningDelta"]
        assert reasoning == ["a", "b", "c", "d"]
        assert TextDelta("inv-text-2", "e") in events
        assert events[1] == StepStarted()

    async def test_unkeyed_tool_chunks_continue_the_open_call(self):
        stream = scripted(
            chunk(tool_call_chunks=[{"name": "a", "args": "{", "id": None, "index": None}]),
            chunk(tool_call_chunks=[{"name": None, "args": "}", "id": None, "index": None}]),
            chunk(tool_call_chunks=[{"name": "b", "args": "", "id": None, "index": 1}]),
        )

        events = [e async for e in stream.events()]

        assert [e for e in events if isinstance(e, ToolInputAvailable)] == [
            ToolInputAvailable("inv-call-1", "a", {}),
            ToolInputAvailable("inv-call-2", "b", {}),
        ]

    async def test_interleaved_tool_chunks_are_tracked_per_index(self):
        stream = scripted(
            event("on_chat_model_start"),
            chunk(tool_call_chunks=[{"name": "search", "args": '{"q":', "id": "c1", "index": 0}]),
            chunk(tool_call_chunks=[{"name": "weather", "args": '{"city":', "id": "c2", "index": 1}]),
            chunk(tool_call_chunks=[{"name": None, "args": '"py"}', "id": None, "index": 0}]),
            chunk(tool_call_chunks=[{"name": None, "args": '"Oslo"}', "id": None, "index": 1}]),
            event(
                "on_chat_model_end",
                output=AIMessage(
                    content="",
                    tool_calls=[
                        ToolCall(name="search", args={"q": "py"}, id="c1"),
                        ToolCall(name="weather", args={"city": "Oslo"}, id="c2"),
                    ],
                ),
            ),
        )

        events = [e async for e in stream.events()]

        assert events[2:10] == [
            ToolInputStarted("c1", "search"),
            ToolInputDelta("c1", '{"q":'),
            ToolInputStarted("c2", "weather"),
            ToolInputDelta("c2", '{"city":'),
            ToolInputDelta("c1", '"py"}'),
            ToolInputDelta("c2", '"Oslo"}'),
            ToolInputAvailable("c1", "search", {"q": "py"}),
            ToolInputAvailable("c2", "weather", {"city": "Oslo"}),
        ]

    async def test_tool_input_comes_from_the_parsed_calls(self):
        stream = scripted(
            chunk(tool_call_chunks=[{"name": "search", "args": "{'q': py", "id": "c1", "index": 0}]),
            event(
                "on_chat_model_end",
                output=AIMessage(content="", tool_calls=[ToolCall(name="search", args={"q": "py"}, id="c1")]),
            ),
        )

        events = [e async for e in stream.events()]

        assert ToolInputAvailable("c1", "search", {"q": "py"}) in events

    async def test_tool_start_waits_for_a_name(self):
        stream = scripted(
            chunk(tool_call_chunks=[{"name": None, "args": '{"q":', "id": None, "index": 0}]),
            chunk(tool_call_chunks=[{"name": "search", "args": '"py"}', "id": "c1", "index": 0}]),
        )

        events = [e async for e in stream.events()]

        assert events[2:5] == [
            ToolInputStarted("c1", "search"),
            ToolInputDelta("c1", '{"q":"py"}'),
            ToolInputAvailable("c1", "search", {"q": "py"}),
        ]

    async def test_nameless_call_takes_its_name_from_the_parsed_call(self):
        stream = scripted(
            chunk(tool_call_chunks=[{"name": None, "args": "{}", "id": None, "index": 0}]),
            event(
                "on_chat_model_end",
                output=AIMessage(content="", tool_calls=[ToolCall(name="search", args={}, id="c1")]),
            ),
            event("on_tool_end", output=ToolMessage(content="ok", tool_call_id="c1", name="search")),
        )

        events = [e async for e in stream.events()]

        assert events[2:6] == [
            ToolInputStarted("c1", "search"),
            ToolInputDelta("c1", "{}"),
            ToolInputAvailable("c1", "search", {}),
            ToolOutputAvailable("c1", "search", "ok"),
        ]

    async def test_tool_outputs_are_matched_by_call_id(self):
        stream = scripted(
            event(
                "on_chat_model_end",
                output=AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="a", args={}, id="c1"), ToolCall(name="b", args={}, id="c2")],
                ),
            ),
            event("on_tool_end", output=ToolMessage(content="second", tool_call_id="c2")),
            event("on_tool_end", output=ToolMessage(content="first", tool_call_id="c1")),
        )

        events = [e async for e in stream.events()]

        assert [e for e in events if isinstance(e, ToolOutputAvailable)] == [
            ToolOutputAvailable("c2", "b", "second"),
            ToolOutputAvailable("c1", "a", "first"),
        ]

    async def test_tool_outputs_without_an_id_fall_back_to_call_order(self):
        stream = scripted(
            event(
                "on_chat_model_end",
                output=AIMessage(
                    content="",
                    tool_calls=[ToolCall(name="a", args={}, id="c1"), ToolCall(name="b", args={}, id="c2")],
                ),
            ),
            event("on_tool_end", output="first"),
            event("on_tool_end", output="second"),
        )

        events = [e async for e in stream.events()]

        assert [e for e in events if isinstance(e, ToolOutputAvailable)] == [
            ToolOutputAvailable("c1", "a", "first"),
            ToolOutputAvailable("c2", "b", "second"),
        ]

    async def test_generated_call_ids_are_aliased_for_outputs(self):
        stream = scripted(
            chunk(tool_call_chunks=[{"name": "a", "args": "{}", "id": None, "index": 0}]),
            event(
                "on_chat_model_end",
                output=AIMessage(content="", tool_calls=[ToolCall(name="a", args={}, id="late")]),
            ),
            event("on_tool_end", output=ToolMessage(content="ok", tool_call_id="late")),
        )

        events = [e async for e in stream.events()]

        assert ToolOutputAvailable("inv-call-1", "a", "ok") in events

    async def test_open_part_is_closed_before_a_failure(self):
        error = RuntimeError("boom")
        events = [e async for e in scripted(chunk("Hi"), error=error).events()]

        assert events[-2:] == [TextEnded("inv-text-1"), StreamFailed(error)]

    async def test_stream_can_only_be_consumed_once(self):
        stream = scripted(*TEXT_STREAM)
        [e async for e in stream.events()]

        with pytest.raises(RuntimeError):
            stream.events()
        with pytest.raises(RuntimeError):
            aiter(stream)

    async def test_error_becomes_a_failure_event(self):
        error = RuntimeError("boom")
        events = [e async for e in scripted(chunk("Hi"), error=error).events()]

        assert events[-1] == StreamFailed(error)
        assert StreamFinished() not in events


class TestVercelDataProtocol:
    async def test_text_stream(self):
        assert await encoded(VercelDataProtocol(), scripted(*TEXT_STREAM)) == [
            {"type": "start", "messageId": "inv"},
            {"type": "start-step"},
            {"type": "text-start", "id": "inv-text-1"},
            {"type": "text-delta", "id": "inv-text-1", "delta": "Hello"},
            {"type": "text-delta", "id": "inv-text-1", "delta": " world"},
            {"type": "text-end", "id": "inv-text-1"},
            {"type": "finish-step"},
            {"type": "finish"},
            "[DONE]",
        ]

    async def test_tool_stream(self):
        parts = await encoded(VercelDataProtocol(), scripted(*TOOL_STREAM))

        assert parts[5:] == [
            {"type": "tool-input-start", "toolCallId": "call_1", "toolName": "search"},
            {"type": "tool-input-delta", "toolCallId": "call_1", "inputTextDelta": '{"q":'},
            {"type": "tool-input-delta", "toolCallId": "call_1", "inputTextDelta": '"py"}'},
            {"type": "tool-input-available", "toolCallId": "call_1", "toolName": "search", "input": {"q": "py"}},
            {"type": "tool-output-available", "toolCallId": "call_1", "output": {"jobs": 2}},
            {"type": "finish-step"},
            {"type": "finish"},
            "[DONE]",
        ]

    async def test_reasoning_stream(self):
        parts = await encoded(VercelDataProtocol(), scripted(*REASONING_STREAM))

        assert parts[2:7] == [
            {"type": "reasoning-start", "id": "inv-reasoning-1"},
            {"type": "reasoning-delta", "id": "inv-reasoning-1", "delta": "Hmm"},
            {"type": "reasoning-end", "id": "inv-reasoning-1"},
            {"type": "text-start", "id": "inv-text-2"},
            {"type": "text-delta", "id": "inv-text-2", "delta": "Done"},
        ]

    async def test_error_stream(self):
        parts = await encoded(VercelDataProtocol(), scripted(chunk("Hi"), error=RuntimeError("secret")))

        assert parts[-3:] == [
            {"type": "text-end", "id": "inv-text-1"},
            {"type": "error", "errorText": "An error occurred."},
            "[DONE]",
        ]

    async def test_error_text_can_be_overridden(self):
        class Verbose(VercelDataProtocol):
            def error_text(self, error: Exception) -> str:
                return str(error)

        parts = await encoded(Verbose(), scripted(error=RuntimeError("secret")))

        assert {"type": "error", "errorText": "secret"} in parts

    def test_unknown_event_is_rejected(self):
        with pytest.raises(TypeError):
            VercelDataProtocol().part(cast(Any, object()))


class TestAgentUserInteractionProtocol:
    async def test_text_stream_uses_invocation_id_by_default(self):
        assert await encoded(AgentUserInteractionProtocol(), scripted(*TEXT_STREAM)) == [
            {"type": "RUN_STARTED", "threadId": "inv", "runId": "inv"},
            {"type": "STEP_STARTED", "stepName": "step-1"},
            {"type": "TEXT_MESSAGE_START", "messageId": "inv-text-1", "role": "assistant"},
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": "inv-text-1", "delta": "Hello"},
            {"type": "TEXT_MESSAGE_CONTENT", "messageId": "inv-text-1", "delta": " world"},
            {"type": "TEXT_MESSAGE_END", "messageId": "inv-text-1"},
            {"type": "STEP_FINISHED", "stepName": "step-1"},
            {"type": "RUN_FINISHED", "threadId": "inv", "runId": "inv"},
        ]

    async def test_thread_defaults_to_conversation_id(self):
        stream = scripted(*TEXT_STREAM)
        stream.conversation_id = "conv"

        parts = await encoded(AgentUserInteractionProtocol(), stream)

        assert parts[0] == {"type": "RUN_STARTED", "threadId": "conv", "runId": "inv"}

    async def test_explicit_ids_override_defaults(self):
        stream = scripted(*TEXT_STREAM)
        stream.conversation_id = "conv"

        parts = await encoded(AgentUserInteractionProtocol(thread_id="t", run_id="r"), stream)

        assert parts[0] == {"type": "RUN_STARTED", "threadId": "t", "runId": "r"}
        assert parts[-1] == {"type": "RUN_FINISHED", "threadId": "t", "runId": "r"}

    async def test_tool_stream(self):
        parts = await encoded(AgentUserInteractionProtocol(), scripted(*TOOL_STREAM))

        assert parts[4:11] == [
            {"type": "TEXT_MESSAGE_END", "messageId": "inv-text-1"},
            {
                "type": "TOOL_CALL_START",
                "toolCallId": "call_1",
                "toolCallName": "search",
                "parentMessageId": "inv-text-1",
            },
            {"type": "TOOL_CALL_ARGS", "toolCallId": "call_1", "delta": '{"q":'},
            {"type": "TOOL_CALL_ARGS", "toolCallId": "call_1", "delta": '"py"}'},
            {"type": "TOOL_CALL_END", "toolCallId": "call_1"},
            {
                "type": "TOOL_CALL_RESULT",
                "messageId": "call_1-result",
                "toolCallId": "call_1",
                "content": '{"jobs": 2}',
                "role": "tool",
            },
            {"type": "STEP_FINISHED", "stepName": "step-1"},
        ]

    async def test_string_tool_result_is_sent_as_is(self):
        stream = scripted(event("on_tool_end", output=ToolMessage(content="ok", tool_call_id="t1")))

        parts = await encoded(AgentUserInteractionProtocol(), stream)

        assert parts[1]["content"] == "ok"

    async def test_reasoning_stream(self):
        parts = await encoded(AgentUserInteractionProtocol(), scripted(*REASONING_STREAM))

        assert parts[2:7] == [
            {"type": "REASONING_START", "messageId": "inv-reasoning-1"},
            {"type": "REASONING_MESSAGE_START", "messageId": "inv-reasoning-1", "role": "reasoning"},
            {"type": "REASONING_MESSAGE_CONTENT", "messageId": "inv-reasoning-1", "delta": "Hmm"},
            {"type": "REASONING_MESSAGE_END", "messageId": "inv-reasoning-1"},
            {"type": "REASONING_END", "messageId": "inv-reasoning-1"},
        ]

    async def test_error_stream(self):
        parts = await encoded(AgentUserInteractionProtocol(), scripted(chunk("Hi"), error=RuntimeError("secret")))

        assert parts[-2:] == [
            {"type": "TEXT_MESSAGE_END", "messageId": "inv-text-1"},
            {"type": "RUN_ERROR", "message": "An error occurred."},
        ]
        assert all(part["type"] != "RUN_FINISHED" for part in parts)

    async def test_tool_call_without_text_has_no_parent_message(self):
        stream = scripted(
            event("on_chat_model_start"),
            chunk("Hi"),
            event("on_chat_model_start"),
            chunk(tool_call_chunks=[{"name": "search", "args": "{}", "id": "c1", "index": 0}]),
        )

        parts = await encoded(AgentUserInteractionProtocol(), stream)

        start = next(part for part in parts if part["type"] == "TOOL_CALL_START")
        assert start == {"type": "TOOL_CALL_START", "toolCallId": "c1", "toolCallName": "search"}


class LineProtocol(StreamProtocol):
    media_type = "text/plain"

    async def encode(self, stream: StreamableAgentResponse) -> AsyncIterator[str]:
        async for item in stream.events():
            if isinstance(item, TextDelta):
                yield item.delta


class TestCustomProtocol:
    async def test_using_protocol_returns_its_streaming_response(self):
        response = scripted(*TEXT_STREAM).using_protocol(LineProtocol())

        body = "".join([part async for part in response.body_iterator])

        assert body == "Hello world"
        assert response.media_type == "text/plain"

    def test_sse_encodes_payloads(self):
        assert StreamProtocol.sse({"a": "é"}) == 'data: {"a":"é"}\n\n'
        assert StreamProtocol.sse("[DONE]") == "data: [DONE]\n\n"
        assert StreamProtocol.sse("a\nb") == "data: a\ndata: b\n\n"


class TestDisconnect:
    async def test_closing_the_response_closes_the_agent_stream(self):
        closed: list[bool] = []
        response = scripted(*TEXT_STREAM, closed=closed).using_vercel_data_protocol()
        body = cast(Any, response.body_iterator)

        await anext(body)
        await anext(body)
        await body.aclose()

        assert closed == [True]


class StreamingToolFake(GenericFakeChatModel):
    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        message = cast(AIMessage, next(self.messages))
        content = message.content if isinstance(message.content, str) else str(message.content)
        for token in re.split(r"(\s)", content):
            if token:
                yield ChatGenerationChunk(message=AIMessageChunk(content=token, id=message.id))
        if message.tool_calls:
            chunks = [
                {"name": c["name"], "args": json.dumps(c.get("args", {})), "id": c.get("id"), "index": i}
                for i, c in enumerate(message.tool_calls)
            ]
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks, id=message.id))


@tool
def search_jobs(query: str) -> str:
    """Search the job board for roles matching the query."""
    return "Python Developer at Shopify"


class SalesCoach(Agent):
    conversation_id = "conversation-7"

    def tools(self):
        return [search_jobs]


@pytest.fixture
def ai_config():
    container = app()
    container.bind("ai", AIConfig())
    container.make("config").set("ai", AIConfig())
    yield
    Ai.reset_fakes()


@pytest.fixture
def client(ai_config):
    api = FastAPI()

    @api.post("/vercel")
    async def vercel():
        return SalesCoach().stream("find python jobs").using_vercel_data_protocol()

    @api.post("/ag-ui")
    async def ag_ui():
        return SalesCoach().stream("find python jobs").using_agent_user_interaction_protocol(run_id="run-1")

    return TestClient(api)


TOOL_TURN = AIMessage(
    content="Searching",
    tool_calls=[ToolCall(name="search_jobs", args={"query": "python"}, id="call_1", type="tool_call")],
)


class TestRoutes:
    def test_vercel_route(self, client):
        Ai._fakes[SalesCoach.__name__] = StreamingToolFake(messages=iter([TOOL_TURN]))

        response = client.post("/vercel")

        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-vercel-ai-ui-message-stream"] == "v1"
        assert response.headers["cache-control"] == "no-cache"
        parts = frames(response.text)
        assert parts[0]["type"] == "start"
        assert {
            "type": "tool-output-available",
            "toolCallId": "call_1",
            "output": "Python Developer at Shopify",
        } in parts
        assert parts[-2:] == [{"type": "finish"}, "[DONE]"]

    def test_ag_ui_route(self, client):
        Ai.fake(SalesCoach.__name__, ["Hi there"])

        response = client.post("/ag-ui")

        assert response.headers["content-type"].startswith("text/event-stream")
        parts = frames(response.text)
        assert parts[0] == {"type": "RUN_STARTED", "threadId": "conversation-7", "runId": "run-1"}
        text = "".join(part["delta"] for part in parts if part["type"] == "TEXT_MESSAGE_CONTENT")
        assert text == "Hi there"
        assert parts[-1] == {"type": "RUN_FINISHED", "threadId": "conversation-7", "runId": "run-1"}


class TestAgentFakeStream:
    async def test_fake_stream_supports_protocols(self, ai_config):
        fake = SalesCoach.fake(["Hello"])
        with fake:
            stream = fake.stream("hi")
            response = stream.using_vercel_data_protocol()
            parts = frames("".join([part async for part in response.body_iterator]))

        assert stream.conversation_id == "conversation-7"
        assert {"type": "text-delta", "id": f"{stream.invocation_id}-text-1", "delta": "Hello"} in parts
        fake.assert_prompted(times=1)

    async def test_fake_stream_still_iterates_raw_events(self, ai_config):
        with SalesCoach.fake(["Hello"]) as fake:
            events = [e async for e in fake.stream("hi")]

        assert events[0]["event"] == "on_chat_model_start"
