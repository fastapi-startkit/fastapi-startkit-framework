from __future__ import annotations

import json
import logging
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
    id: str | None = None
    name: str = ""
    args: str = ""
    started: bool = False


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
        self._open: TextStarted | ReasoningStarted | None = None
        self._step_open = False
        self._drafts: dict[Any, _ToolDraft] = {}
        self._pending_outputs: list[ToolInputAvailable] = []
        self._aliases: dict[str, str] = {}
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
            for normalized in self._close_part():
                yield normalized
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
            yield from self._close_part()
            yield from self._finish_tool_calls(getattr(data.get("output"), "tool_calls", None) or [])
        elif kind == "on_tool_end":
            yield from self._tool_output(data.get("output"))

    def _open_step(self) -> Iterator[StreamEvent]:
        self._step_open = True
        yield StepStarted()

    def _close_step(self) -> Iterator[StreamEvent]:
        yield from self._close_part()
        yield from self._finish_tool_calls([])
        if self._step_open:
            self._step_open = False
            yield StepFinished()

    def _close_part(self) -> Iterator[StreamEvent]:
        part, self._open = self._open, None
        if isinstance(part, TextStarted):
            yield TextEnded(part.id)
        elif isinstance(part, ReasoningStarted):
            yield ReasoningEnded(part.id)

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

    def _draft_key(self, call: dict[str, Any]) -> Any:
        for key in (call.get("index"), call.get("id")):
            if key is not None:
                return key
        return next(reversed(self._drafts), 0)

    def _tool_chunk(self, call: dict[str, Any]) -> Iterator[StreamEvent]:
        key = self._draft_key(call)
        draft = self._drafts.get(key)
        if draft is None:
            yield from self._close_part()
            draft = self._drafts[key] = _ToolDraft()
        draft.id = draft.id or call.get("id")
        draft.name = draft.name or call.get("name") or ""
        arguments = call.get("args") or ""
        draft.args += arguments
        if draft.started:
            if arguments:
                yield ToolInputDelta(draft.id or "", arguments)
        elif draft.name:
            yield from self._start_draft(draft)

    def _start_draft(self, draft: _ToolDraft) -> Iterator[StreamEvent]:
        draft.id = draft.id or self._new_id("call")
        draft.started = True
        yield ToolInputStarted(draft.id, draft.name)
        if draft.args:
            yield ToolInputDelta(draft.id, draft.args)

    def _match_draft(self, call: dict[str, Any], drafts: list[_ToolDraft], parsed_ids: set[Any]) -> _ToolDraft | None:
        by_id = next((draft for draft in drafts if draft.id and draft.id == call.get("id")), None)
        return by_id or next((draft for draft in drafts if draft.id not in parsed_ids), None)

    def _finish_tool_calls(self, calls: list[dict[str, Any]]) -> Iterator[StreamEvent]:
        drafts = list(self._drafts.values())
        self._drafts = {}
        parsed_ids = {call.get("id") for call in calls if call.get("id")}
        for call in calls:
            draft = self._match_draft(call, drafts, parsed_ids) or _ToolDraft(id=call.get("id"))
            if draft in drafts:
                drafts.remove(draft)
            arguments = call.get("args") or {}
            draft.name = call["name"]
            if not draft.started:
                draft.id = draft.id or call.get("id")
                draft.args = draft.args or json.dumps(arguments, default=str)
                yield from self._start_draft(draft)
            if call.get("id") and call["id"] != draft.id:
                self._aliases[call["id"]] = draft.id or ""
            yield self._tool_input_available(draft.id or "", draft.name, arguments)
        for draft in drafts:
            if draft.started:
                yield self._tool_input_available(draft.id or "", draft.name, _decode_json(draft.args or "{}", {}))

    def _tool_input_available(self, call_id: str, name: str, arguments: Any) -> ToolInputAvailable:
        available = ToolInputAvailable(call_id, name, arguments)
        self._pending_outputs.append(available)
        return available

    def _tool_output(self, output: Any) -> Iterator[StreamEvent]:
        yield from self._close_part()
        content = getattr(output, "content", output)
        tool_call_id = getattr(output, "tool_call_id", None)
        if tool_call_id:
            target = self._aliases.get(tool_call_id, tool_call_id)
            call = next((pending for pending in self._pending_outputs if pending.id == target), None)
        else:
            call = self._pending_outputs[0] if self._pending_outputs else None
        if call is not None:
            self._pending_outputs.remove(call)
            call_id, name = call.id, call.name
        else:
            call_id = tool_call_id or self._new_id("call")
            name = getattr(output, "name", None) or ""
        yield ToolOutputAvailable(call_id, name, _decode_json(content, content))
