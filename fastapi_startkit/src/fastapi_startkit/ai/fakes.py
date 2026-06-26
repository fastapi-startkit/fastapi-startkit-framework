from __future__ import annotations

import json
import re
from typing import Any, Iterable


def _require_langchain():
    try:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
    except ImportError as exc:
        raise ImportError(
            "The agent test harness requires the 'ai' extra. Install it with: pip install \"fastapi-startkit[ai]\""
        ) from exc
    return GenericFakeChatModel, AIMessage


def fake_chat_model(turns: Iterable[Any]):
    generic_model, ai_message = _require_langchain()

    from langchain_core.messages import AIMessageChunk
    from langchain_core.outputs import ChatGenerationChunk

    class _FakeChatModel(generic_model):
        def bind_tools(self, tools, **kwargs):
            return self

        def _stream(self, messages, stop=None, run_manager=None, **kwargs):
            message = next(self.messages)
            if not isinstance(message, ai_message):
                message = ai_message(content=str(message))

            content = message.content if isinstance(message.content, str) else str(message.content)
            for token in re.split(r"(\s)", content):
                if token:
                    yield ChatGenerationChunk(message=AIMessageChunk(content=token, id=message.id))

            tool_calls = list(message.tool_calls or [])
            if tool_calls:
                chunks = [
                    {
                        "name": call["name"],
                        "args": json.dumps(call.get("args", {})),
                        "id": call.get("id"),
                        "index": index,
                    }
                    for index, call in enumerate(tool_calls)
                ]
                yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=chunks, id=message.id))

    normalized = [t if isinstance(t, ai_message) else ai_message(content=str(t)) for t in turns]
    return _FakeChatModel(messages=iter(normalized))
