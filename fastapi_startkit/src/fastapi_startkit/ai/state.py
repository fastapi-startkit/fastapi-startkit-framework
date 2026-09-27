"""Helpers over the ``{"messages": [...]}`` state a prompt() returns.

An agent turn is the same shape langchain's ``create_agent().invoke()`` yields:
``HumanMessage``, then the model's ``AIMessage`` (carrying ``tool_calls``), then
one ``ToolMessage`` per tool result — plus ``"structured_response"`` when the
agent has a schema. AI/tool messages carry their ``response_time`` (ms) in
``additional_kwargs``.
"""

from __future__ import annotations

import json
from typing import Any


def messages(state: dict | None) -> list:
    return (state or {}).get("messages") or []


def text(state: dict | None) -> str:
    """The turn's final content — the last message's text (a tool-run turn ends
    on the tool's result, a plain turn on the model's answer)."""
    turn = messages(state)
    if not turn:
        return ""
    content = turn[-1].content
    return content if isinstance(content, str) else str(content)


def tool_calls(state: dict | None) -> list[dict]:
    """Every tool call the model requested across the turn's AI messages."""
    return [call for m in messages(state) if m.type == "ai" for call in (getattr(m, "tool_calls", None) or [])]


def tool_events(state: dict | None) -> list[dict]:
    """Each executed tool as {name, args, id, content, content_type, response_time} —
    the requested call joined with its ToolMessage result (by call id, falling
    back to order for replayed turns that don't store ids)."""
    pending = list(tool_calls(state))
    events: list[dict] = []
    for m in messages(state):
        if m.type != "tool":
            continue
        call_id = getattr(m, "tool_call_id", "") or ""
        call = next((c for c in pending if c.get("id") == call_id), None) or (pending[0] if pending else {})
        if call in pending:
            pending.remove(call)
        content = m.content if isinstance(m.content, str) else str(m.content)
        events.append(
            {
                "name": call.get("name") or m.name,
                "args": call.get("args", {}),
                "id": call.get("id") or call_id or None,
                "content": content,
                "content_type": _content_type(content),
                "response_time": (m.additional_kwargs or {}).get("response_time", 0.0),
            }
        )
    return events


def usage(state: dict | None) -> dict:
    """Summed token usage across the turn's AI messages: {"input", "output"}."""
    totals = {"input": 0, "output": 0}
    for m in messages(state):
        meta = getattr(m, "usage_metadata", None) or {}
        totals["input"] += meta.get("input_tokens", 0)
        totals["output"] += meta.get("output_tokens", 0)
    return totals


def runtime(state: dict | None) -> float:
    """Seconds spent on the turn's model and tool calls, summed from each
    message's recorded ``response_time`` (ms)."""
    total_ms = sum((m.additional_kwargs or {}).get("response_time", 0.0) for m in messages(state))
    return total_ms / 1000


def structured(state: dict | None) -> Any:
    return (state or {}).get("structured_response")


def _content_type(content: str) -> str:
    try:
        json.loads(content)
    except (ValueError, TypeError):
        return "text"
    return "json"
