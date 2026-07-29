from __future__ import annotations

import inspect
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from . import recording
from .pipeline import Response, build_pipeline

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document

Message = BaseMessage | dict[str, Any]


def _as_text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


def _stream_event(event: str, name: str, run_id: str, data: dict) -> dict:
    """A StandardStreamEvent dict, the shape LangChain's astream_events yields."""
    return {"event": event, "name": name, "run_id": run_id, "tags": [], "metadata": {}, "parent_ids": [], "data": data}


class BaseRunner(ABC):
    def __init__(self, agent: Agent) -> None:
        self.agent = agent
        self._reset_capture()
        # Populated by stream() so the record-and-replay harness can persist the
        # same structured turn a buffered prompt() produces.
        self.last_response: dict | None = None

    def _reset_capture(self) -> None:
        """Clear the per-turn interaction captured across the model/tool calls."""
        self._transcript: list[dict] = []
        self._tool_events: list[dict] = []
        self._requested_tool_calls: list[dict] = []
        self._usage: dict = {}

    @staticmethod
    def _usage_from_message(message: Any) -> dict:
        meta = getattr(message, "usage_metadata", None)
        if not meta:
            return {}
        return {"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0)}

    def _record_ai_message(
        self, message: BaseMessage, response_time_ms: float, chunks: list[str] | None = None
    ) -> None:
        content = message.content if isinstance(message.content, str) else str(message.content)
        tool_calls = list(getattr(message, "tool_calls", None) or [])
        uses = recording.uses_from_usage_metadata(getattr(message, "usage_metadata", None))
        self._transcript.append(
            recording.ai(
                content=content, tool_calls=tool_calls, uses=uses, response_time=response_time_ms, chunks=chunks
            )
        )
        if tool_calls:
            self._requested_tool_calls = tool_calls
        if getattr(message, "usage_metadata", None):
            self._usage = {"input": uses["input_token"], "output": uses["output_token"]}

    def _record_tool_message(self, call: ToolCall, message: BaseMessage, response_time_ms: float) -> None:
        content = message.content if isinstance(message.content, str) else str(message.content)
        entry = recording.tool_response(content=content, response_time=response_time_ms)
        self._transcript.append(entry)
        self._tool_events.append(
            {
                "name": call["name"],
                "args": call.get("args", {}),
                "id": call.get("id"),
                "content": content,
                "content_type": entry["content_type"],
                "response_time": response_time_ms,
            }
        )

    def _turn_messages(self, message: str) -> list[BaseMessage]:
        """Rebuild the turn as LangChain messages — [HumanMessage, AIMessage,
        ToolMessage, ...] — mirroring create_agent().invoke() output. Each AI and
        tool message carries its ``response_time`` (ms) in ``additional_kwargs``."""
        from langchain_core.messages import HumanMessage, ToolMessage  # noqa: PLC0415

        messages: list[BaseMessage] = [HumanMessage(content=message)] if message else []
        tool_events = iter(self._tool_events)
        for entry in self._transcript:
            if entry["type"] == "ai":
                uses = entry.get("uses") or {}
                messages.append(
                    AIMessage(
                        content=entry.get("content", ""),
                        tool_calls=entry.get("tool_calls") or [],
                        additional_kwargs={"response_time": entry.get("response_time", 0.0)},
                        usage_metadata={
                            "input_tokens": uses.get("input_token", 0),
                            "output_tokens": uses.get("output_token", 0),
                            "total_tokens": uses.get("total_token", 0),
                            "input_token_details": {"cache_read": uses.get("cache_token", 0)},
                        }
                        if uses
                        else None,
                    )
                )
            elif entry["type"] == "tool_response":
                event = next(tool_events, {})
                messages.append(
                    ToolMessage(
                        content=entry.get("content", ""),
                        name=event.get("name"),
                        tool_call_id=event.get("id") or "",
                        additional_kwargs={"response_time": entry.get("response_time", 0.0)},
                    )
                )
        return messages

    async def _build_messages(self, message: str, attachments: list[Document] | None = None) -> list[dict]:
        agent = self.agent
        messages: list[dict] = []

        instruction = agent.instructions()
        if instruction:
            messages.append({"role": "system", "content": instruction})

        # messages() may be sync (return a list) or async (agents that read
        # their history from a database); support both.
        history = agent.messages()
        if inspect.isawaitable(history):
            history = await history
        messages.extend(history or [])

        if message:
            messages.append({"role": "user", "content": message})

        if attachments:
            content: Any = [{"type": "text", "text": message}]
            for doc in attachments:
                content.append(doc.to_langchain_block())
            messages.append({"role": "user", "content": content})

        return messages

    def _build_model(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        from .ai import Ai  # noqa: PLC0415

        return Ai().get_model_for(self.agent, model, provider_options)

    def _apply_schema(self, state: dict) -> dict:
        from . import state as agent_state  # noqa: PLC0415

        schema = self.agent.schema()
        if schema is not None and state.get("structured_response") is None and agent_state.text(state):
            state["structured_response"] = self._build_schema(schema, agent_state.text(state))
        return state

    @staticmethod
    def _build_schema(schema: Any, content: str) -> Any:
        import json  # noqa: PLC0415

        if hasattr(schema, "model_validate_json"):
            return schema.model_validate_json(content)
        if hasattr(schema, "model_validate"):
            return schema.model_validate(json.loads(content))
        return schema(**json.loads(content))

    @abstractmethod
    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> dict: ...

    @abstractmethod
    def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]: ...


class Runner(BaseRunner):
    async def run(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> dict:
        self._reset_capture()
        messages = await self._build_messages(message, attachments)
        model = self._build_model(model, provider_options)

        parsed = await self._run_pipeline(model, messages)
        state: dict = {"messages": self._turn_messages(message)}
        if parsed is not None:
            state["structured_response"] = parsed
        return self._apply_schema(state)

    async def _run_pipeline(self, chat_model: Any, messages: list) -> Any:
        """Run the turn through the middleware pipeline; the interaction lands on
        the capture buffers. Returns the parsed structured output, if any."""
        chain = list(self.agent.middleware())
        if not chain:
            raw = await self._invoke(chat_model, messages)
            return self._parsed_of(raw)

        def core(model: Any) -> Response:
            async def _run() -> AsyncIterator[Any]:
                yield await self._invoke(model, messages)

            return Response(_run)

        pipeline = build_pipeline(chain, core)
        raw = await pipeline(chat_model)
        return self._parsed_of(raw)

    @staticmethod
    def _parsed_of(result: Any) -> Any:
        # A structured-output model returns {"parsed": ..., "raw": AIMessage}.
        if isinstance(result, dict) and "parsed" in result:
            return result.get("parsed")
        return None

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[dict]:
        self._reset_capture()
        messages = await self._build_messages(message)
        chat_model = self._build_model(model, provider_options)
        chain = list(self.agent.middleware())

        def core(m: Any) -> Response:
            return Response(lambda: self._invoke_stream(m, messages))

        pipeline = build_pipeline(chain, core) if chain else core

        async for chunk in pipeline(chat_model):
            yield chunk

        # Expose the same structured turn a buffered prompt() returns, so the
        # record-and-replay harness can persist streamed runs identically.
        self.last_response = {"messages": self._turn_messages(message)}

    async def _invoke(self, model: Runnable[Any, BaseMessage], messages: list) -> BaseMessage:
        started = time.perf_counter()
        response: AIMessage = await model.ainvoke(list(messages))  # type: ignore[assignment]
        latency_ms = (time.perf_counter() - started) * 1000
        if isinstance(response, dict) and "parsed" in response:
            # Structured output: record the raw model turn so it lands on the
            # state's messages alongside the parsed object.
            raw = response.get("raw")
            if raw is not None:
                self._record_ai_message(raw, latency_ms)
            return response  # type: ignore[return-value]
        self._record_ai_message(response, latency_ms)
        if not response.tool_calls:
            return response
        return (await self._run_tools(response.tool_calls))[-1]

    async def _invoke_stream(self, model: Runnable[Any, BaseMessage], messages: list) -> AsyncIterator[dict]:
        """Yield the same StandardStreamEvent dicts LangChain's astream_events
        produces: on_chat_model_(start|stream|end) for the model turn, then
        on_tool_(start|end) around each tool execution."""
        import uuid  # noqa: PLC0415

        started = time.perf_counter()
        run_id = str(uuid.uuid4())
        model_name = type(model).__name__
        payload = {"messages": [list(messages)]}
        yield _stream_event("on_chat_model_start", model_name, run_id, {"input": payload})

        gathered: AIMessageChunk | None = None
        chunks: list[str] = []
        async for chunk in model.astream(list(messages)):
            if chunk.content:
                chunks.append(_as_text(chunk.content))
            yield _stream_event("on_chat_model_stream", model_name, run_id, {"chunk": chunk})
            gathered = chunk if gathered is None else gathered + chunk  # type: ignore[operator]

        latency_ms = (time.perf_counter() - started) * 1000
        if gathered is None:
            return
        yield _stream_event("on_chat_model_end", model_name, run_id, {"output": gathered, "input": payload})
        self._record_ai_message(gathered, latency_ms, chunks=chunks)
        if not gathered.tool_calls:
            return
        for call in gathered.tool_calls:
            tool_run_id = str(uuid.uuid4())
            yield _stream_event("on_tool_start", call["name"], tool_run_id, {"input": call.get("args", {})})
            message = await self._run_tool(call)
            yield _stream_event("on_tool_end", call["name"], tool_run_id, {"output": message})

    async def _run_tools(self, tool_calls: list[ToolCall]) -> list[BaseMessage]:
        return [await self._run_tool(call) for call in tool_calls]

    async def _run_tool(self, call: ToolCall) -> BaseMessage:
        tools: dict[str, BaseTool] = {tool.name: tool for tool in self.agent.tools()}
        try:
            selected = tools[call["name"]]
        except KeyError:
            raise ValueError(f"Agent has no tool named {call['name']!r}") from None
        started = time.perf_counter()
        message = await selected.ainvoke(call)
        self._record_tool_message(call, message, (time.perf_counter() - started) * 1000)
        return message
