from __future__ import annotations

import json
import logging
from collections import deque
from collections.abc import AsyncGenerator, Iterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import Any

from .events import (
    ReasoningDelta,
    ReasoningEnded,
    ReasoningStarted,
    StepFinished,
    StepStarted,
    StreamEvent,
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

logger = logging.getLogger(__name__)


@dataclass
class _ToolDraft:
    key: Any
    id: str
    name: str
    args: str = ""


def _decode_json(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except ValueError:
        return fallback


def _block_part(block: Any) -> tuple[str, str]:
    if isinstance(block, str):
        return "text", block
    kind = block.get("type")
    if kind == "text":
        return "text", block.get("text") or ""
    if kind == "thinking":
        return "reasoning", block.get("thinking") or ""
    if kind == "reasoning":
        summary = "".join(item.get("text", "") for item in block.get("summary") or [] if isinstance(item, dict))
        return "reasoning", block.get("reasoning") or summary
    if kind == "reasoning_content":
        return "reasoning", (block.get("reasoning_content") or {}).get("text") or ""
    return "text", ""


def _content_parts(chunk: Any) -> list[tuple[str, str]]:
    content = getattr(chunk, "content", "")
    parts = [("text", content)] if isinstance(content, str) else [_block_part(block) for block in content]
    reasoning = (getattr(chunk, "additional_kwargs", None) or {}).get("reasoning_content")
    if isinstance(reasoning, str):
        parts.insert(0, ("reasoning", reasoning))
    return [(kind, text) for kind, text in parts if text]


class EventNormalizer:
    def __init__(self, message_id: str) -> None:
        self.message_id = message_id
        self._open: TextStarted | ReasoningStarted | _ToolDraft | None = None
        self._step_open = False
        self._streamed_calls = 0
        self._pending_outputs: deque[ToolInputAvailable] = deque()
        self._ids = 0

    async def normalize(self, source: AsyncGenerator[dict[str, Any], None]) -> AsyncGenerator[StreamEvent, None]:
        yield StreamStarted(self.message_id)
        try:
            async with aclosing(source) as events:
                async for event in events:
                    for normalized in self._translate(event):
                        yield normalized
        except Exception as error:
            logger.exception("Agent stream failed")
            yield StreamFailed(error)
            return
        for normalized in self._close_step():
            yield normalized
        yield StreamFinished()

    def _new_id(self, kind: str) -> str:
        self._ids += 1
        return f"{self.message_id}-{kind}-{self._ids}"

    def _translate(self, event: dict[str, Any]) -> Iterator[StreamEvent]:
        kind = event.get("event")
        data = event.get("data") or {}
        if kind == "on_chat_model_start":
            yield from self._close_step()
            yield from self._open_step()
        elif kind == "on_chat_model_stream":
            yield from self._chunk(data.get("chunk"))
        elif kind == "on_chat_model_end":
            yield from self._finish_tool_calls(data.get("output"))
        elif kind == "on_tool_end":
            yield from self._tool_output(data.get("output"))

    def _open_step(self) -> Iterator[StreamEvent]:
        self._step_open = True
        self._streamed_calls = 0
        yield StepStarted()

    def _close_step(self) -> Iterator[StreamEvent]:
        yield from self._close_part()
        if self._step_open:
            self._step_open = False
            yield StepFinished()

    def _close_part(self) -> Iterator[StreamEvent]:
        part, self._open = self._open, None
        if isinstance(part, TextStarted):
            yield TextEnded(part.id)
        elif isinstance(part, ReasoningStarted):
            yield ReasoningEnded(part.id)
        elif isinstance(part, _ToolDraft):
            yield self._tool_input_available(part.id, part.name, _decode_json(part.args or "{}", {}))

    def _tool_input_available(self, call_id: str, name: str, arguments: Any) -> ToolInputAvailable:
        available = ToolInputAvailable(call_id, name, arguments)
        self._pending_outputs.append(available)
        return available

    def _chunk(self, chunk: Any) -> Iterator[StreamEvent]:
        if not self._step_open:
            yield from self._open_step()
        for kind, text in _content_parts(chunk):
            yield from self._delta(kind, text)
        for call in getattr(chunk, "tool_call_chunks", None) or []:
            yield from self._tool_chunk(call)

    def _delta(self, kind: str, text: str) -> Iterator[StreamEvent]:
        started, delta = (TextStarted, TextDelta) if kind == "text" else (ReasoningStarted, ReasoningDelta)
        if not isinstance(self._open, started):
            yield from self._close_part()
            self._open = started(self._new_id(kind))
            yield self._open
        yield delta(self._open.id, text)

    def _tool_chunk(self, call: dict[str, Any]) -> Iterator[StreamEvent]:
        key = call.get("index") if call.get("index") is not None else call.get("id")
        draft = self._open if isinstance(self._open, _ToolDraft) else None
        if draft is None or (key is not None and key != draft.key):
            yield from self._close_part()
            draft = _ToolDraft(key, call.get("id") or self._new_id("call"), call.get("name") or "")
            self._open = draft
            self._streamed_calls += 1
            yield ToolInputStarted(draft.id, draft.name)
        if arguments := call.get("args"):
            draft.args += arguments
            yield ToolInputDelta(draft.id, arguments)

    def _finish_tool_calls(self, output: Any) -> Iterator[StreamEvent]:
        yield from self._close_part()
        for call in (getattr(output, "tool_calls", None) or [])[self._streamed_calls :]:
            call_id = call.get("id") or self._new_id("call")
            arguments = call.get("args") or {}
            yield ToolInputStarted(call_id, call["name"])
            yield ToolInputDelta(call_id, json.dumps(arguments, default=str))
            yield self._tool_input_available(call_id, call["name"], arguments)

    def _tool_output(self, output: Any) -> Iterator[StreamEvent]:
        yield from self._close_part()
        content = getattr(output, "content", output)
        if self._pending_outputs:
            call = self._pending_outputs.popleft()
            call_id, name = call.id, call.name
        else:
            call_id = getattr(output, "tool_call_id", None) or self._new_id("call")
            name = getattr(output, "name", None) or ""
        yield ToolOutputAvailable(call_id, name, _decode_json(content, content))
