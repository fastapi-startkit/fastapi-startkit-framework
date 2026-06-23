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
from .lab import Lab
from .response import AgentResponse, AgentSnapshot


class Agent:
    """
    Base class for all agents. Subclass this and override lifecycle methods.

    Class-level configuration (set via decorators or subclass attributes)::

        _instructions   = ""            # the agent's static system instructions
        _provider       = "anthropic"   # LLM provider
        _model          = ""            # model ID (empty = provider default)
        _max_steps      = 10            # max agentic loop iterations
        _max_tokens     = 4096          # max output tokens
        _timeout        = 30.0          # request timeout in seconds
        _top_p          = 1.0           # top-p nucleus sampling
        _memory_backend = ""            # memory backend name (reserved)
    """

    _instructions: str = ""
    _provider: str = "anthropic"
    _model: str = ""
    _max_steps: int = 10
    _max_tokens: int = 4096
    _timeout: float = 30.0
    _top_p: float = 1.0
    _memory_backend: str = ""

    def __init__(self):
        self._fakes: dict[str, AgentResponse | AgentSnapshot] = {}
        self._call_log: list[dict] = []

    def messages(self) -> list[dict]:
        return []

    def instructions(self) -> str | None:
        return None

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
            model: str | None = None,
            attachments: list[Document] | None = None,
            provider_options: dict | None = None,
    ) -> AgentResponse:
        """Send a prompt and return an AgentResponse."""
        message = self.before(message)

        _run_kwargs = dict(
            model=model,
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
        yield from self._stream(message, model=model, provider_options=provider_options)

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

    def _resolve_model(self, override: str | None = None) -> str:
        # Lab.get_model() returns the given model if truthy, else the config default.
        return Lab(self._provider).get_model(override or self._model or None)

    def _get_provider_options(self, override: dict | None = None) -> dict:
        options = dict(self.provider_options().get(self._provider, {}))
        if override:
            provider_specific = override.get(self._provider, override)
            if isinstance(provider_specific, dict):
                options.update(provider_specific)
        return options

    def _build_instruction(self) -> str | None:
        return self._instructions or self.instructions()

    def _build_messages(
            self,
            message: str,
            attachments: list[Document] | None = None,
    ) -> list[dict]:
        messages: list[dict] = []

        instruction = self._instructions or self.instructions()
        if instruction:
            messages.append({"role": "system", "content": instruction})

        messages.extend(self.messages() or [])

        if message:
            messages.append({"role": "user", "content": message})

        if attachments:
            content: Any = [{"type": "text", "text": message}]
            for doc in attachments:
                content.append(doc.to_langchain_block())
            messages.append({"role": "user", "content": content})

        return messages

    def _build_model(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        """Build a LangChain chat model for this agent.

        This is the seam tests patch to inject a fake chat model (see
        :func:`fastapi_startkit.ai.fakes.fake_chat_model`).
        """
        from langchain.chat_models import init_chat_model  # noqa: PLC0415

        lab = Lab(self._provider)
        kwargs: dict[str, Any] = {"model_provider": lab.get_provider_key()}

        api_key = lab.get_api_key()
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
            model: str | None = None,
            attachments: list[Document] | None = None,
            provider_options: dict | None = None,
    ) -> AgentResponse:
        from .runner import Runner  # noqa: PLC0415

        messages = self._build_messages(message, attachments)
        chat_model = self._build_model(model, provider_options)

        result = Runner(chat_model, self.tools(), self._max_steps).run(messages)
        return self._to_agent_response(result)

    def _stream(
            self,
            message: str,
            model: str | None = None,
            provider_options: dict | None = None,
    ) -> Iterator[str]:
        from .runner import StreamRunner  # noqa: PLC0415

        messages = self._build_messages(message)
        chat_model = self._build_model(model, provider_options)

        yield from StreamRunner(chat_model, self.tools(), self._max_steps).run(messages)
