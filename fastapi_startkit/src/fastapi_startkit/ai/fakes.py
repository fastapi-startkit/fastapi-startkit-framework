"""LangChain test helpers — drive a real agent loop offline, without a provider.

:func:`fake_chat_model` returns a chat model that replays a scripted sequence of
assistant turns. Inject it into an :class:`~fastapi_startkit.ai.Agent` by patching
``_build_model`` so :meth:`Agent.prompt` runs the genuine ``Runner`` loop —
tool calls included — with no network. Requires the ``ai`` extra::

    pip install "fastapi-startkit[ai]"

The runner does not feed tool results back into the model, so a single
tool-calling turn returns the tool's output directly.

Example — exercise a tool-calling agent end to end::

    from langchain_core.messages import AIMessage, ToolCall
    from fastapi_startkit.ai import fake_chat_model

    model = fake_chat_model([
        AIMessage(content="", tool_calls=[
            ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call"),
        ]),
    ])
    agent = JobAssistant()
    agent._build_model = lambda *a, **k: model
    response = await agent.prompt("find me a python job")
    assert response.content == "Python Developer at Shopify"
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable


def _require_langchain():
    try:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "The agent test harness requires the 'ai' extra. "
            'Install it with: pip install "fastapi-startkit[ai]"'
        ) from exc
    return GenericFakeChatModel, AIMessage


def fake_chat_model(turns: Iterable[Any]):
    """Return a fake chat model that replays ``turns`` in order.

    Each turn is an ``AIMessage`` (which may carry ``tool_calls``) or a ``str``
    (shorthand for ``AIMessage(content=...)``). The scripted turns already encode
    the model's decisions, so ``bind_tools`` is a no-op — the bound tool schemas
    don't change what the fake says next.

    Unlike the stock ``GenericFakeChatModel``, this fake streams ``tool_calls`` as
    well as text. A scripted tool-calling turn therefore reaches ``StreamRunner``
    with its tool calls intact, so the runner executes the tools and streams their
    output — the same path a real provider takes.
    """
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
                yield ChatGenerationChunk(
                    message=AIMessageChunk(content="", tool_call_chunks=chunks, id=message.id)
                )

    normalized = [t if isinstance(t, ai_message) else ai_message(content=str(t)) for t in turns]
    return _FakeChatModel(messages=iter(normalized))
