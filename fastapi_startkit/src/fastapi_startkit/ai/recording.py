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
from dataclasses import dataclass, field
from typing import Any

from .response import AgentResponse


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


def uses_from_agent_usage(usage: dict | None) -> dict:
    """Map an :class:`AgentResponse` ``usage`` ({input, output}) onto ``uses``."""
    usage = usage or {}
    inp = usage.get("input", 0)
    out = usage.get("output", 0)
    return {"input_token": inp, "output_token": out, "cache_token": 0, "total_token": inp + out}


def is_transcript(value: Any) -> bool:
    """True when ``value`` is a new-format ordered transcript (list of typed entries)."""
    return isinstance(value, list) and bool(value) and isinstance(value[0], dict) and "type" in value[0]


@dataclass
class HumanMessage:
    content: str

    def to_dict(self) -> dict:
        return {"type": "human", "content": self.content}


@dataclass
class AIMessage:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    uses: dict = field(default_factory=dict)
    response_time: float = 0.0
    chunks: list[str] | None = None

    def to_dict(self) -> dict:
        entry: dict[str, Any] = {"type": "ai"}
        if self.content:
            entry["content"] = self.content
        if self.tool_calls:
            entry["tool_calls"] = self.tool_calls
        entry["uses"] = self.uses
        entry["response_time"] = self.response_time
        if self.chunks is not None:
            entry["chunks"] = self.chunks
        return entry


@dataclass
class ToolCallMessage:
    content: str
    response_time: float = 0.0
    content_type: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": "tool_response",
            "content_type": self.content_type or _infer_content_type(self.content),
            "content": self.content,
            "response_time": self.response_time,
        }


def _usage_from_uses(uses: dict) -> dict:
    return {"input": uses.get("input_token", 0), "output": uses.get("output_token", 0)}


def to_response(transcript: list[dict]) -> AgentResponse:
    """Reconstruct an :class:`AgentResponse` from a recorded turn transcript.

    The final ``ai`` answer supplies the response content; if the turn stopped at
    a tool call (no follow-up answer), the tool result stands in as the content.
    """
    content = ""
    tool_calls: list[dict] = []
    usage: dict = {}
    tool_events: list[dict] = []
    runtime = 0.0

    for entry in transcript:
        kind = entry.get("type")
        if kind == "ai":
            if entry.get("tool_calls"):
                tool_calls.extend(entry["tool_calls"])
            if entry.get("content"):
                content = entry["content"]
            if entry.get("uses"):
                usage = _usage_from_uses(entry["uses"])
            runtime += (entry.get("response_time") or 0) / 1000
        elif kind == "tool_response":
            tool_events.append(
                {
                    "content": entry.get("content", ""),
                    "content_type": entry.get("content_type"),
                    "response_time": entry.get("response_time", 0),
                }
            )
            if not content:
                content = entry.get("content", "")
            runtime += (entry.get("response_time") or 0) / 1000

    return AgentResponse(content=content, tool_calls=tool_calls, usage=usage, tool_events=tool_events, runtime=runtime)


def chunks_from_transcript(transcript: list[dict]) -> list[str]:
    """Collect streamed chunks recorded on the turn's ``ai`` messages."""
    chunks: list[str] = []
    for entry in transcript:
        if entry.get("type") == "ai" and entry.get("chunks"):
            chunks.extend(entry["chunks"])
    return chunks
