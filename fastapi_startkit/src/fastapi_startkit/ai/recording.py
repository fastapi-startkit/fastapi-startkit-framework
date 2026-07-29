"""Ordered per-turn recording format for ``Agent.record()`` cassettes.

A recorded turn is an ordered list of message dicts that captures the full
interaction for one user input — the human prompt, every model turn (with its
token ``uses`` and ``response_time``), and every tool call (with the tool's
response and its own ``response_time``). Persisting the whole ordered exchange —
rather than only the final answer — lets recordings be replayed and inspected
faithfully.

    [
      {"type": "human", "content": "suggest me jobs"},
      {"type": "ai", "tool_calls": [...], "uses": {...}, "response_time": 12.0},
      {"type": "tool_response", "content_type": "json", "content": "[...]", "response_time": 5.0},
      {"type": "ai", "content": "Here is a job...", "uses": {...}, "response_time": 8.0},
    ]

``response_time`` is milliseconds; ``uses`` mirrors LangChain ``usage_metadata``
as ``input_token`` / ``output_token`` / ``cache_token`` / ``total_token``.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def _infer_content_type(content: str) -> str:
    try:
        json.loads(content)
    except (ValueError, TypeError):
        return "text"
    return "json"


def uses_from_usage_metadata(meta: dict | None) -> dict:
    """Map a LangChain ``usage_metadata`` dict onto the cassette ``uses`` shape."""
    meta = meta or {}
    details = meta.get("input_token_details") or {}
    return {
        "input_token": meta.get("input_tokens", 0),
        "output_token": meta.get("output_tokens", 0),
        "cache_token": details.get("cache_read", 0),
        "total_token": meta.get("total_tokens", 0),
    }


def is_transcript(value: Any) -> bool:
    """True when ``value`` is a new-format ordered transcript (list of typed entries)."""
    return isinstance(value, list) and bool(value) and isinstance(value[0], dict) and "type" in value[0]


def human(content: str) -> dict:
    """Build a ``human`` transcript entry."""
    return {"type": "human", "content": content}


def ai(
    content: str = "",
    tool_calls: list[dict] | None = None,
    uses: dict | None = None,
    response_time: float = 0.0,
    chunks: list[str] | None = None,
) -> dict:
    """Build an ``ai`` transcript entry (a model turn: answer and/or tool calls)."""
    entry: dict[str, Any] = {"type": "ai"}
    if content:
        entry["content"] = content
    if tool_calls:
        entry["tool_calls"] = tool_calls
    entry["uses"] = uses or {}
    entry["response_time"] = response_time
    if chunks is not None:
        entry["chunks"] = chunks
    return entry


def tool_response(content: str, response_time: float = 0.0, content_type: str | None = None) -> dict:
    """Build a ``tool_response`` transcript entry (a tool's output)."""
    return {
        "type": "tool_response",
        "content_type": content_type or _infer_content_type(content),
        "content": content,
        "response_time": response_time,
    }


def usage_metadata_from_uses(uses: dict) -> dict:
    """Map a cassette ``uses`` dict back onto LangChain ``usage_metadata``."""
    return {
        "input_tokens": uses.get("input_token", 0),
        "output_tokens": uses.get("output_token", 0),
        "total_tokens": uses.get("total_token", 0),
        "input_token_details": {"cache_read": uses.get("cache_token", 0)},
    }


def _as_text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


def entries_from_messages(messages: list[BaseMessage]) -> list[dict]:
    """Convert a turn's AI/tool LangChain messages into cassette entries.

    Human (and system) messages are skipped — the cassette turn opens with its
    own ``human`` entry. ``response_time`` is read from ``additional_kwargs``,
    where the runner stamps it on every AI and tool message."""
    entries: list[dict] = []
    for message in messages or []:
        kind = getattr(message, "type", "")
        response_time = (getattr(message, "additional_kwargs", None) or {}).get("response_time", 0.0)
        if kind == "ai":
            entries.append(
                ai(
                    content=_as_text(message.content),
                    tool_calls=list(getattr(message, "tool_calls", None) or []),
                    uses=uses_from_usage_metadata(getattr(message, "usage_metadata", None)),
                    response_time=response_time,
                )
            )
        elif kind == "tool":
            entries.append(tool_response(content=_as_text(message.content), response_time=response_time))
    return entries


def messages_from_transcript(transcript: list[dict]) -> list[BaseMessage]:
    """Rebuild the turn's LangChain messages from cassette entries, so a replayed
    response carries the same ``messages`` a live run produces. Cassette entries
    don't store the tool's name/call id, so those stay empty on replay."""
    messages: list[BaseMessage] = []
    for entry in transcript:
        kind = entry.get("type")
        if kind == "human":
            messages.append(HumanMessage(content=entry.get("content", "")))
        elif kind == "ai":
            uses = entry.get("uses") or {}
            messages.append(
                AIMessage(
                    content=entry.get("content", ""),
                    tool_calls=entry.get("tool_calls") or [],
                    additional_kwargs={"response_time": entry.get("response_time", 0.0)},
                    usage_metadata=usage_metadata_from_uses(uses) if uses else None,
                )
            )
        elif kind == "tool_response":
            messages.append(
                ToolMessage(
                    content=entry.get("content", ""),
                    tool_call_id="",
                    additional_kwargs={"response_time": entry.get("response_time", 0.0)},
                )
            )
    return messages


def to_state(transcript: list[dict]) -> dict:
    """Reconstruct a turn's ``{"messages": [...]}`` state from cassette entries,
    so a replayed turn has the same shape a live run returns."""
    return {"messages": messages_from_transcript(transcript)}


def accumulate_uses(messages: list, totals: dict) -> None:
    """Add every AI message's token usage in a turn's ``messages`` into ``totals``
    (keys: input, output, cache, total)."""
    for message in messages or []:
        if getattr(message, "type", "") != "ai":
            continue
        uses = uses_from_usage_metadata(getattr(message, "usage_metadata", None))
        totals["input"] += uses["input_token"]
        totals["output"] += uses["output_token"]
        totals["cache"] += uses["cache_token"]
        totals["total"] += uses["total_token"]


def chunks_from_transcript(transcript: list[dict]) -> list[str]:
    """Collect streamed chunks recorded on the turn's ``ai`` messages."""
    chunks: list[str] = []
    for entry in transcript:
        if entry.get("type") == "ai" and entry.get("chunks"):
            chunks.extend(entry["chunks"])
    return chunks
