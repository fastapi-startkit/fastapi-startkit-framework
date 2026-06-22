"""LangChain test-harness helpers — run agents offline, without a real provider.

These utilities let tests exercise a *real* LangChain agent (``create_agent``)
without calling a model API, by replaying a scripted sequence of assistant turns
through a fake chat model. They require the ``langchain`` extra::

    pip install "fastapi-startkit[langchain]"

Example — drive a full tool-calling loop with no network::

    from langchain_core.messages import AIMessage, ToolCall
    from langchain.agents import create_agent
    from fastapi_startkit.ai import fake_chat_model

    model = fake_chat_model([
        AIMessage(content="", tool_calls=[
            ToolCall(name="search_jobs", args={"query": "python"}, id="c1", type="tool_call"),
        ]),
        AIMessage(content="Here is a Python Developer role at Shopify."),
    ])
    agent = create_agent(model=model, tools=[search_jobs])
    result = agent.invoke({"messages": [{"role": "user", "content": "Find me a python job"}]})
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from .response import AgentResponse

if TYPE_CHECKING:
    from langchain_core.messages import AIMessage


def _require_langchain():
    try:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "LangChain is required for the agent test harness. "
            "Install it with: pip install \"fastapi-startkit[langchain]\""
        ) from exc
    return GenericFakeChatModel, AIMessage


def fake_chat_model(turns: Iterable[Any]):
    """Return a fake chat model that replays ``turns`` in order.

    Each turn is an ``AIMessage`` (which may carry ``tool_calls``) or a ``str``
    (shorthand for ``AIMessage(content=...)``). Pass the result straight to
    ``langchain.agents.create_agent(model=..., tools=[...])`` to run a complete
    agent loop — tool calls included — without hitting a real provider.
    """
    generic_model, ai_message = _require_langchain()

    class _FakeChatModel(generic_model):
        # create_agent calls bind_tools() when tools are present; GenericFakeChatModel
        # leaves it unimplemented. The scripted turns already encode the model's
        # decisions, so the bound tool schemas are irrelevant — binding is a no-op.
        def bind_tools(self, tools, **kwargs):
            return self

    normalized = [t if isinstance(t, ai_message) else ai_message(content=str(t)) for t in turns]
    return _FakeChatModel(messages=iter(normalized))


def is_ai_message(value: Any) -> bool:
    """Return True if ``value`` is a LangChain ``AIMessage`` (False if langchain is absent)."""
    try:
        from langchain_core.messages import AIMessage
    except ImportError:
        return False
    return isinstance(value, AIMessage)


def to_agent_response(value: "AIMessage") -> AgentResponse:
    """Convert a LangChain ``AIMessage`` into an :class:`AgentResponse`."""
    _, ai_message = _require_langchain()
    if not isinstance(value, ai_message):
        raise TypeError(f"Expected an AIMessage, got {type(value)!r}")

    content = value.content if isinstance(value.content, str) else str(value.content)
    tool_calls = list(getattr(value, "tool_calls", None) or [])

    usage: dict = {}
    meta = getattr(value, "usage_metadata", None)
    if meta:
        usage = {
            "input": meta.get("input_tokens", 0),
            "output": meta.get("output_tokens", 0),
        }

    return AgentResponse(content=content, tool_calls=tool_calls, usage=usage, raw=value)
