from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import TYPE_CHECKING, Any, override

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
from .protocol import StreamProtocol

if TYPE_CHECKING:
    from .response import StreamableAgentResponse


class VercelDataProtocol(StreamProtocol):
    @override
    def headers(self) -> dict[str, str]:
        return {**super().headers(), "x-vercel-ai-ui-message-stream": "v1"}

    def error_text(self, error: Exception) -> str:
        return "An error occurred."

    async def encode(self, stream: StreamableAgentResponse) -> AsyncIterator[str]:
        async with aclosing(stream.events()) as events:
            async for event in events:
                yield self.sse(self.part(event))
        yield self.sse("[DONE]")

    def part(self, event: StreamEvent) -> dict[str, Any]:
        match event:
            case StreamStarted(message_id):
                return {"type": "start", "messageId": message_id}
            case StepStarted():
                return {"type": "start-step"}
            case TextStarted(part_id):
                return {"type": "text-start", "id": part_id}
            case TextDelta(part_id, delta):
                return {"type": "text-delta", "id": part_id, "delta": delta}
            case TextEnded(part_id):
                return {"type": "text-end", "id": part_id}
            case ReasoningStarted(part_id):
                return {"type": "reasoning-start", "id": part_id}
            case ReasoningDelta(part_id, delta):
                return {"type": "reasoning-delta", "id": part_id, "delta": delta}
            case ReasoningEnded(part_id):
                return {"type": "reasoning-end", "id": part_id}
            case ToolInputStarted(call_id, name):
                return {"type": "tool-input-start", "toolCallId": call_id, "toolName": name}
            case ToolInputDelta(call_id, delta):
                return {"type": "tool-input-delta", "toolCallId": call_id, "inputTextDelta": delta}
            case ToolInputAvailable(call_id, name, arguments):
                return {"type": "tool-input-available", "toolCallId": call_id, "toolName": name, "input": arguments}
            case ToolOutputAvailable(call_id, _, output):
                return {"type": "tool-output-available", "toolCallId": call_id, "output": output}
            case StepFinished():
                return {"type": "finish-step"}
            case StreamFinished():
                return {"type": "finish"}
            case StreamFailed(error):
                return {"type": "error", "errorText": self.error_text(error)}
        raise TypeError(f"Unknown stream event {event!r}")
