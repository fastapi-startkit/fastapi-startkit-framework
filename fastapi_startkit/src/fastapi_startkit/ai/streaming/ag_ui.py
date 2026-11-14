from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import aclosing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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


@dataclass
class _Run:
    thread_id: str
    run_id: str
    step: int = 0


class AgentUserInteractionProtocol(StreamProtocol):
    def __init__(self, thread_id: str | None = None, run_id: str | None = None) -> None:
        self.thread_id = thread_id
        self.run_id = run_id

    def error_message(self, error: Exception) -> str:
        return "An error occurred."

    async def encode(self, stream: StreamableAgentResponse) -> AsyncIterator[str]:
        run = _Run(
            thread_id=self.thread_id or stream.conversation_id or stream.invocation_id,
            run_id=self.run_id or stream.invocation_id,
        )
        async with aclosing(stream.events()) as events:
            async for event in events:
                for payload in self.payloads(event, run):
                    yield self.sse(payload)

    def payloads(self, event: StreamEvent, run: _Run) -> Iterator[dict[str, Any]]:
        match event:
            case StreamStarted():
                yield {"type": "RUN_STARTED", "threadId": run.thread_id, "runId": run.run_id}
            case StepStarted():
                run.step += 1
                yield {"type": "STEP_STARTED", "stepName": f"step-{run.step}"}
            case TextStarted(message_id):
                yield {"type": "TEXT_MESSAGE_START", "messageId": message_id, "role": "assistant"}
            case TextDelta(message_id, delta):
                yield {"type": "TEXT_MESSAGE_CONTENT", "messageId": message_id, "delta": delta}
            case TextEnded(message_id):
                yield {"type": "TEXT_MESSAGE_END", "messageId": message_id}
            case ReasoningStarted(message_id):
                yield {"type": "REASONING_START", "messageId": message_id}
                yield {"type": "REASONING_MESSAGE_START", "messageId": message_id, "role": "reasoning"}
            case ReasoningDelta(message_id, delta):
                yield {"type": "REASONING_MESSAGE_CONTENT", "messageId": message_id, "delta": delta}
            case ReasoningEnded(message_id):
                yield {"type": "REASONING_MESSAGE_END", "messageId": message_id}
                yield {"type": "REASONING_END", "messageId": message_id}
            case ToolInputStarted(call_id, name):
                yield {"type": "TOOL_CALL_START", "toolCallId": call_id, "toolCallName": name}
            case ToolInputDelta(call_id, delta):
                yield {"type": "TOOL_CALL_ARGS", "toolCallId": call_id, "delta": delta}
            case ToolInputAvailable(call_id):
                yield {"type": "TOOL_CALL_END", "toolCallId": call_id}
            case ToolOutputAvailable(call_id, _, output):
                yield {
                    "type": "TOOL_CALL_RESULT",
                    "messageId": f"{call_id}-result",
                    "toolCallId": call_id,
                    "content": output if isinstance(output, str) else json.dumps(output, default=str),
                    "role": "tool",
                }
            case StepFinished():
                yield {"type": "STEP_FINISHED", "stepName": f"step-{run.step}"}
            case StreamFinished():
                yield {"type": "RUN_FINISHED", "threadId": run.thread_id, "runId": run.run_id}
            case StreamFailed(error):
                yield {"type": "RUN_ERROR", "message": self.error_message(error)}
