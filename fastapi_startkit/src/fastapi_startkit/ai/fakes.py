"""LangChain test helpers — drive a real agent loop offline, without a provider.

:func:`fake_chat_model` returns a chat model that replays a scripted sequence of
assistant turns. Inject it into an :class:`~fastapi_startkit.ai.Agent` by patching
``_build_model`` so :meth:`Agent.prompt` runs the genuine ``create_agent`` loop —
tool calls included — with no network. Requires the ``langgraph`` extra::

    pip install "fastapi-startkit[langgraph]"

Example — exercise a tool-calling agent end to end::

    from langchain_core.messages import AIMessage, ToolCall
    from fastapi_startkit.ai import fake_chat_model

    model = fake_chat_model([
        AIMessage(content="", tool_calls=[
            ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call"),
        ]),
        AIMessage(content="Here is a Python Developer role at Shopify."),
    ])
    agent = JobAssistant()
    agent._build_model = lambda *a, **k: model
    response = await agent.prompt("find me a python job")
    assert response.content == "Here is a Python Developer role at Shopify."
"""

from __future__ import annotations

from typing import Any, Iterable


def _require_langchain():
    try:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "The agent test harness requires the 'langgraph' extra. "
            'Install it with: pip install "fastapi-startkit[langgraph]"'
        ) from exc
    return GenericFakeChatModel, AIMessage


def fake_chat_model(turns: Iterable[Any]):
    """Return a fake chat model that replays ``turns`` in order.

    Each turn is an ``AIMessage`` (which may carry ``tool_calls``) or a ``str``
    (shorthand for ``AIMessage(content=...)``). The scripted turns already encode
    the model's decisions, so ``bind_tools`` is a no-op — the bound tool schemas
    don't change what the fake says next.
    """
    generic_model, ai_message = _require_langchain()

    class _FakeChatModel(generic_model):
        def bind_tools(self, tools, **kwargs):
            return self

    normalized = [t if isinstance(t, ai_message) else ai_message(content=str(t)) for t in turns]
    return _FakeChatModel(messages=iter(normalized))
