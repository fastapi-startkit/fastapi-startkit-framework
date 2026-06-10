"""Agent base class — subclass this and apply decorators to build an AI agent."""

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
                content.append(doc.to_anthropic_block())
            history.append({"role": "user", "content": content})
        else:
            history.append({"role": "user", "content": message})

        return resolved_system, history

    def _run(
        self,
        message: str,
        system: str | None = None,
        model: str | None = None,
        extra_messages: list[dict] | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        resolved_system, messages = self._build_messages(message, system, extra_messages, attachments)
        resolved_model = self._resolve_model(model)
        options = self._get_provider_options(provider_options)

        if self._provider == "anthropic":
            return self._run_anthropic(resolved_system, messages, resolved_model, options)
        if self._provider == "openai":
            return self._run_openai(resolved_system, messages, resolved_model, options)
        if self._provider == "google":
            return self._run_google(resolved_system, messages, resolved_model, options)
        raise ValueError(f"Unsupported provider: {self._provider!r}. Use 'anthropic', 'openai', or 'google'.")

    def _stream(
        self,
        message: str,
        system: str | None = None,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> Iterator[str]:
        resolved_system, messages = self._build_messages(message, system)
        resolved_model = self._resolve_model(model)
        options = self._get_provider_options(provider_options)

        if self._provider == "anthropic":
            yield from self._stream_anthropic(resolved_system, messages, resolved_model, options)
        elif self._provider == "openai":
            yield from self._stream_openai(resolved_system, messages, resolved_model, options)
        elif self._provider == "google":
            yield from self._stream_google(resolved_system, messages, resolved_model, options)
        else:
            raise ValueError(f"Unsupported provider: {self._provider!r}. Use 'anthropic', 'openai', or 'google'.")

    # ── Anthropic ──────────────────────────────────────────────────────────

    def _run_anthropic(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> AgentResponse:
        from anthropic import Anthropic

        client = Anthropic()
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": messages,
            **options,
        }
        if system:
            params["system"] = system

        resp = client.messages.create(**params)
        content = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return AgentResponse(
            content=content,
            usage={"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
            raw=resp,
        )

    def _stream_anthropic(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> Iterator[str]:
        from anthropic import Anthropic

        client = Anthropic()
        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": messages,
            **options,
        }
        if system:
            params["system"] = system

        with client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield text

    # ── OpenAI ─────────────────────────────────────────────────────────────

    def _run_openai(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> AgentResponse:
        from openai import OpenAI

        client = OpenAI()
        all_messages: list[dict] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": all_messages,
            **options,
        }
        resp = client.chat.completions.create(**params)
        content = resp.choices[0].message.content or ""
        return AgentResponse(
            content=content,
            usage={
                "input": resp.usage.prompt_tokens if resp.usage else 0,
                "output": resp.usage.completion_tokens if resp.usage else 0,
            },
            raw=resp,
        )

    def _stream_openai(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> Iterator[str]:
        from openai import OpenAI

        client = OpenAI()
        all_messages: list[dict] = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        params: dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": all_messages,
            "stream": True,
            **options,
        }
        for chunk in client.chat.completions.create(**params):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # ── Google ─────────────────────────────────────────────────────────────

    def _resolve_google_api_key(self) -> str:
        """
        Resolve the Google API key.

        Tries Config.get("ai").providers["google"].key first,
        then falls back to GEMINI_API_KEY / GOOGLE_API_KEY env vars.
        """
        import os  # noqa: PLC0415

        try:
            from fastapi_startkit.facades.Config import Config  # noqa: PLC0415

            ai_config = Config.get("ai")
            providers = getattr(ai_config, "providers", {})
            google_cfg = providers.get("google")
            if google_cfg is not None:
                key = getattr(google_cfg, "key", None)
                if key:
                    return key
        except Exception:
            pass
        return os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")

    def _run_google(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> AgentResponse:
        import google.generativeai as genai  # noqa: PLC0415

        api_key = self._resolve_google_api_key()
        if api_key:
            genai.configure(api_key=api_key)

        generation_config: dict[str, Any] = {}
        if self._max_tokens:
            generation_config["max_output_tokens"] = self._max_tokens
        if self._top_p != 1.0:
            generation_config["top_p"] = self._top_p
        generation_config.update(options)

        google_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
            generation_config=generation_config if generation_config else None,
        )

        google_messages = _to_google_messages(messages)
        response = google_model.generate_content(google_messages)
        content = response.text if hasattr(response, "text") else ""
        usage: dict[str, Any] = {}
        if hasattr(response, "usage_metadata"):
            meta = response.usage_metadata
            usage = {
                "input": getattr(meta, "prompt_token_count", 0),
                "output": getattr(meta, "candidates_token_count", 0),
            }
        return AgentResponse(content=content, usage=usage, raw=response)

    def _stream_google(
        self,
        system: str | None,
        messages: list[dict],
        model: str,
        options: dict,
    ) -> Iterator[str]:
        import google.generativeai as genai  # noqa: PLC0415

        api_key = self._resolve_google_api_key()
        if api_key:
            genai.configure(api_key=api_key)

        generation_config: dict[str, Any] = {}
        if self._max_tokens:
            generation_config["max_output_tokens"] = self._max_tokens
        if self._top_p != 1.0:
            generation_config["top_p"] = self._top_p
        generation_config.update(options)

        google_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system,
            generation_config=generation_config if generation_config else None,
        )

        google_messages = _to_google_messages(messages)
        for chunk in google_model.generate_content(google_messages, stream=True):
            if chunk.text:
                yield chunk.text


# ─── Utilities ─────────────────────────────────────────────────────────────────


def _to_google_messages(messages: list[dict]) -> list[dict]:
    """
    Convert OpenAI-style messages to Google GenerativeAI content format.
    Maps 'assistant' role → 'model'; omits 'system' (handled via system_instruction).
    """
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            continue  # system_instruction is set at model-construction level
        google_role = "model" if role == "assistant" else "user"
        if isinstance(content, list):
            # Multi-part content — extract text parts only
            text = " ".join(p.get("text", "") for p in content if isinstance(p, dict) and "text" in p)
            result.append({"role": google_role, "parts": [{"text": text}]})
        else:
            result.append({"role": google_role, "parts": [{"text": str(content)}]})
    return result
