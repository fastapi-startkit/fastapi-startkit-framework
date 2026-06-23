"""Agent base class — subclass this and apply decorators to build an AI agent.

The agent runs on LangChain/LangGraph: :meth:`Agent.prompt` builds a chat model
with ``init_chat_model`` and drives a ``create_agent`` loop (tools included),
while :meth:`Agent.stream` streams tokens straight from the model. The public
surface — ``prompt``/``stream``/``fake``/``assert_prompted``/``reset`` plus the
lifecycle hooks and decorators — is provider-agnostic; only the backend changed.

Real calls need the ``langgraph`` extra plus the relevant provider integration
(e.g. ``langchain-anthropic``). Tests never need them: :meth:`fake` short-circuits
before the backend, and :func:`fastapi_startkit.ai.fakes.fake_chat_model` drives
the full agent loop offline.
"""

from __future__ import annotations

import fnmatch
from typing import Any, Callable, Iterator, Optional, Type

from .document import Document
from .response import AgentResponse, AgentSnapshot


class Agent:
    """
    Base class for all agents. Subclass this and override lifecycle methods.

    Class-level configuration (set via decorators or subclass attributes)::

        _provider       = "anthropic"   # LLM provider
        _model          = ""            # model ID (empty = provider default)
        _max_steps      = 10            # max agentic loop iterations
        _max_tokens     = 4096          # max output tokens
        _timeout        = 30.0          # request timeout in seconds
        _top_p          = 1.0           # top-p nucleus sampling
        _memory_backend = ""            # memory backend name (reserved)
    """

    _provider: str = "anthropic"
    _model: str = ""
    _max_steps: int = 10
    _max_tokens: int = 4096
    _timeout: float = 30.0
    _top_p: float = 1.0
    _memory_backend: str = ""

    _DEFAULT_MODELS: dict[str, str] = {
        "anthropic": "claude-sonnet-4-6",
        "openai": "gpt-4o",
        "google": "gemini-2.0-flash",
    }

    # Map the agent's provider name to the LangChain ``init_chat_model`` provider id.
    _LANGCHAIN_PROVIDERS: dict[str, str] = {
        "anthropic": "anthropic",
        "openai": "openai",
        "google": "google_genai",
    }

    def __init__(self):
        self._fakes: dict[str, AgentResponse | AgentSnapshot] = {}
        self._call_log: list[dict] = []

    # ── Lifecycle — override in subclasses ──────────────────────────────────

    def messages(self) -> list[dict]:
        """Return initial messages / few-shot examples."""
        return []

    def schema(self) -> Optional[Type]:
        """Return a Pydantic model class for structured output, or None for plain text."""
        return None

    def tools(self) -> list[Callable]:
        """Return a list of callable tools the agent may invoke."""
        return []

    def middleware(self) -> list[Callable]:
        """Return middleware callables that wrap each LLM request."""
        return []

    def provider_options(self) -> dict:
        """Return provider-specific options keyed by provider name."""
        return {}

    def before(self, message: str) -> str:
        """Called before the message is sent. Return the (possibly modified) message."""
        return message

    def after(self, response: AgentResponse) -> AgentResponse:
        """Called after the LLM responds. Return the (possibly modified) response."""
        return response

    # ── Public API ──────────────────────────────────────────────────────────

    def prompt(
        self,
        message: str,
        *,
        system: str | None = None,
        model: str | None = None,
        messages: list[dict] | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        """Send a prompt and return an AgentResponse."""
        message = self.before(message)

        _run_kwargs = dict(
            system=system,
            model=model,
            extra_messages=messages,
            attachments=attachments,
            provider_options=provider_options,
        )

        match = self._match_fake(message)
        if match is not None:
            if isinstance(match, AgentSnapshot):
                response = match.resolve(self, message, **_run_kwargs)
            else:
                response = match
            self._log_call("prompt", message)
            return self.after(response)

        def _call(msg: str) -> AgentResponse:
            return self._run(msg, **_run_kwargs)

        response = self._apply_middleware(message, _call)
        self._log_call("prompt", message)
        return self.after(response)

    def stream(
        self,
        message: str,
        *,
        system: str | None = None,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> Iterator[str]:
        """Stream a response token by token."""
        message = self.before(message)
        self._log_call("stream", message)
        fake = self._match_fake(message)
        if fake is not None:
            if isinstance(fake, AgentSnapshot):
                response = fake.resolve(self, message)
            else:
                response = fake
            yield response.content
            return
        yield from self._stream(message, system=system, model=model, provider_options=provider_options)

    def fake(self, patterns: dict[str, AgentResponse | AgentSnapshot]) -> "Agent":
        """Register fake responses for testing. Keys are glob patterns."""
        for pattern, value in patterns.items():
            self._fakes[pattern] = value
        return self

    def assert_prompted(self, times: int | None = None) -> None:
        """Assert that prompt() or stream() was called."""
        calls = [c for c in self._call_log if c["method"] in ("prompt", "stream")]
        if times is not None:
            assert len(calls) == times, f"Expected {times} prompt call(s), got {len(calls)}"
        else:
            assert len(calls) > 0, "Expected at least one prompt() or stream() call, but none were made"

    def assert_not_prompted(self) -> None:
        """Assert that prompt() and stream() were never called."""
        self.assert_prompted(times=0)

    def reset(self) -> "Agent":
        """Clear fakes and call log. Useful between test cases."""
        self._fakes.clear()
        self._call_log.clear()
        return self

    # ── Internal helpers ────────────────────────────────────────────────────

    def _match_fake(self, message: str) -> Optional[AgentResponse | AgentSnapshot]:
        for pattern, value in self._fakes.items():
            if fnmatch.fnmatch(message.lower(), pattern.lower()):
                return value
        return None

    def _log_call(self, method: str, message: str) -> None:
        self._call_log.append({"method": method, "message": message})

    def _apply_middleware(self, message: str, final: Callable[[str], AgentResponse]) -> AgentResponse:
        """Build a left-to-right middleware chain and invoke it."""
        chain = list(self.middleware())

        def build(mw_list: list, fn: Callable) -> Callable:
            if not mw_list:
                return fn
            head, *tail = mw_list
            next_fn = build(tail, fn)
            return lambda msg: head(msg, next_fn)

        return build(chain, final)(message)

    def _execute_tool(self, name: str, inputs: dict) -> Any:
        """Find a tool by function name and call it with the given inputs."""
        for tool in self.tools():
            if callable(tool) and tool.__name__ == name:
                return tool(**inputs)
        raise ValueError(f"Tool {name!r} not found")

    def _resolve_model(self, override: str | None = None) -> str:
        if override:
            return override
        if self._model:
            return self._model
        return self._DEFAULT_MODELS.get(self._provider, "")

    def _get_provider_options(self, override: dict | None = None) -> dict:
        options = dict(self.provider_options().get(self._provider, {}))
        if override:
            provider_specific = override.get(self._provider, override)
            if isinstance(provider_specific, dict):
                options.update(provider_specific)
        return options

    def _resolve_api_key(self, provider_name: str) -> str | None:
        """Try Config.get("ai") first, fallback to None (the model reads its env var)."""
        try:
            from fastapi_startkit.facades.Config import Config  # noqa: PLC0415

            ai_config = Config.get("ai")
            return ai_config.providers[provider_name].key or None
        except Exception:
            return None

    def _build_messages(
        self,
        message: str,
        system: str | None = None,
        extra_messages: list[dict] | None = None,
        attachments: list[Document] | None = None,
    ) -> tuple[str | None, list[dict]]:
        base = self.messages()

        resolved_system = system
        if resolved_system is None:
            sys_entries = [m for m in base if m.get("role") == "system"]
            if sys_entries:
                resolved_system = sys_entries[0]["content"]

        history = [m for m in base if m.get("role") != "system"]
        if extra_messages:
            history.extend(extra_messages)

        if attachments:
            content: Any = [{"type": "text", "text": message}]
            for doc in attachments:
                content.append(doc.to_langchain_block())
            history.append({"role": "user", "content": content})
        else:
            history.append({"role": "user", "content": message})

        return resolved_system, history

    def _build_model(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        """Build a LangChain chat model for this agent.

        This is the seam tests patch to inject a fake chat model (see
        :func:`fastapi_startkit.ai.fakes.fake_chat_model`).
        """
        from langchain.chat_models import init_chat_model  # noqa: PLC0415

        provider = self._LANGCHAIN_PROVIDERS.get(self._provider, self._provider)
        kwargs: dict[str, Any] = {"model_provider": provider}

        api_key = self._resolve_api_key(self._provider)
        if api_key:
            kwargs["api_key"] = api_key
        if self._max_tokens:
            kwargs["max_tokens"] = self._max_tokens
        if self._top_p != 1.0:
            kwargs["top_p"] = self._top_p
        if self._timeout:
            kwargs["timeout"] = self._timeout
        kwargs.update(self._get_provider_options(provider_options))

        return init_chat_model(self._resolve_model(model), **kwargs)

    def _to_agent_response(self, result: Any) -> AgentResponse:
        """Map a ``create_agent`` invoke result to an AgentResponse."""
        messages = result.get("messages", []) if isinstance(result, dict) else []
        final = messages[-1] if messages else result

        content = getattr(final, "content", "")
        if not isinstance(content, str):
            content = str(content)

        tool_calls = list(getattr(final, "tool_calls", None) or [])

        usage: dict[str, Any] = {}
        meta = getattr(final, "usage_metadata", None)
        if meta:
            usage = {"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0)}

        return AgentResponse(content=content, tool_calls=tool_calls, usage=usage, raw=result)

    def _run(
        self,
        message: str,
        system: str | None = None,
        model: str | None = None,
        extra_messages: list[dict] | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        from langchain.agents import create_agent  # noqa: PLC0415

        resolved_system, history = self._build_messages(message, system, extra_messages, attachments)
        chat_model = self._build_model(model, provider_options)

        agent_kwargs: dict[str, Any] = {"tools": self.tools()}
        if resolved_system:
            agent_kwargs["system_prompt"] = resolved_system
        schema = self.schema()
        if schema is not None:
            agent_kwargs["response_format"] = schema

        agent = create_agent(chat_model, **agent_kwargs)
        result = agent.invoke({"messages": history}, {"recursion_limit": self._max_steps * 2 + 1})
        return self._to_agent_response(result)

    def _stream(
        self,
        message: str,
        system: str | None = None,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> Iterator[str]:
        resolved_system, history = self._build_messages(message, system)
        chat_model = self._build_model(model, provider_options)

        lc_messages: list[dict] = []
        if resolved_system:
            lc_messages.append({"role": "system", "content": resolved_system})
        lc_messages.extend(history)

        for chunk in chat_model.stream(lc_messages):
            text = getattr(chunk, "content", "")
            if not text:
                continue
            yield text if isinstance(text, str) else str(text)
