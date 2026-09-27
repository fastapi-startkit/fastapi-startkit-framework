import json
import re
from typing import cast

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk


def tool_call_message(query: str) -> AIMessage:
    """A model turn that calls job_search_tool with the given query."""
    return AIMessage(
        content="",
        tool_calls=[{"name": "job_search_tool", "args": {"query": query}, "id": "c1", "type": "tool_call"}],
    )


class StreamingToolFake(GenericFakeChatModel):
    """GenericFakeChatModel can't stream a content-less tool-call message (it yields
    zero chunks -> 'No generations found'). Under astream_events models auto-stream,
    so emit proper tool-call chunks, mirroring the framework's own test fake."""

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
