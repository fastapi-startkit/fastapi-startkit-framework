"""
Agent wrapper — a Laravel-inspired declarative API for building AI agents.

Uses the Anthropic and OpenAI SDKs directly as provider backends.
The public API (Agent, AgentResponse, decorators) is provider-agnostic.

Usage::

    from packages.agent import Agent, AgentResponse, provider, model, max_tokens

    @provider("anthropic")
    @model("claude-sonnet-4-6")
    @max_tokens(2048)
    class SalesAgent(Agent):
        def messages(self):
            return [{"role": "system", "content": "You are a helpful sales assistant."}]

        def tools(self):
            return [lookup_crm, send_email]

        def provider_options(self):
            return {
                "anthropic": {"thinking": {"type": "enabled", "budget_tokens": 1024}},
            }

    agent = SalesAgent()
    response = agent.prompt("Summarize this lead...")
    for chunk in agent.stream("Write a follow-up email..."):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional, Type


# ─── Decorators ────────────────────────────────────────────────────────────────


def provider(name: str):
    """Set the LLM provider: 'anthropic', 'openai', 'google', etc."""
    def decorator(cls):
        cls._provider = name
        return cls
    return decorator


def model(name: str = ""):
    """Set the model identifier (e.g. 'claude-sonnet-4-6', 'gpt-4o')."""
    def decorator(cls):
        cls._model = name
        return cls
    return decorator


def max_steps(n: int = 10):
    """Maximum agentic loop iterations before stopping."""
    def decorator(cls):
        cls._max_steps = n
        return cls
    return decorator


def max_tokens(n: int = 4096):
    """Maximum output tokens per response."""
    def decorator(cls):
        cls._max_tokens = n
        return cls
    return decorator


def timeout(seconds: float = 30.0):
    """Request timeout in seconds."""
    def decorator(cls):
        cls._timeout = seconds
        return cls
    return decorator


def top_p(value: float = 1.0):
    """Top-p nucleus sampling parameter."""
    def decorator(cls):
        cls._top_p = value
        return cls
    return decorator


def memory(backend: str = ""):
    """Attach a named memory backend to this agent."""
    def decorator(cls):
        cls._memory_backend = backend
        return cls
    return decorator


# ─── Response Objects ──────────────────────────────────────────────────────────


@dataclass
class AgentResponse:
    """Returned by Agent.prompt(). Wraps the LLM response."""
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: Any = None

    def text(self) -> str:
        """Return the text content."""
        return self.content

    def json(self) -> Any:
        """Parse the content as JSON."""
        return json.loads(self.content)

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        return bool(self.content)


@dataclass
class AgentSnapshot:
    """
    Record-and-replay snapshot for testing.

    - If the file at ``path`` **does not exist**: the agent calls the real API,
      saves the response as JSON, then returns it.
    - If the file **exists**: the saved response is loaded and returned without
      hitting the API.

    This lets tests run against real responses on first run and be fully
    offline and deterministic on every subsequent run.

    Example::

        agent.fake({"*analyze*": AgentSnapshot(path="tests/fixtures/analysis.json")})
    """
    path: str

    def exists(self) -> bool:
        """Return True if the snapshot file is already recorded."""
        return os.path.exists(self.path)

    def load(self) -> AgentResponse:
        """Load the recorded response from disk."""
        with open(self.path) as f:
            data = json.load(f)
        return AgentResponse(
            content=data.get("content", ""),
            tool_calls=data.get("tool_calls", []),
            usage=data.get("usage", {}),
        )

    def save(self, response: AgentResponse) -> None:
        """Persist a real API response to disk for future replays."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(
                {
                    "content": response.content,
                    "tool_calls": response.tool_calls,
                    "usage": response.usage,
                },
                f,
                indent=2,
            )

    def resolve(self, agent: "Agent", message: str, **run_kwargs: Any) -> AgentResponse:
        """
        Return the response — from disk if recorded, or from the real API
        (which is then saved for future runs).
        """
        if self.exists():
            return self.load()
        response = agent._run(message, **run_kwargs)
        self.save(response)
        return response


# ─── Attachment Helper ─────────────────────────────────────────────────────────


class Document:
    """Attach documents to agent.prompt() calls."""

    def __init__(self, content: str, name: str = "", media_type: str = "text/plain"):
        self.content = content
        self.name = name
        self.media_type = media_type

    @classmethod
    def from_path(cls, path: str) -> "Document":
        """Load a document from a local file path."""
        with open(path) as f:
            content = f.read()
        return cls(content=content, name=path)

    @classmethod
    def from_storage(cls, key: str) -> "Document":
        """Load a document from application storage (storage/<key>)."""
        return cls.from_path(f"storage/{key}")

    def to_anthropic_block(self) -> dict:
        """Return an Anthropic-compatible content block for this document."""
        return {
            "type": "document",
            "source": {"type": "text", "media_type": self.media_type, "data": self.content},
            "title": self.name,
        }


# ─── Agent Base Class ──────────────────────────────────────────────────────────


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

    # Provider → default model
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
        """
        Return initial messages / few-shot examples.
        Use role 'system' for the system prompt.

        Example::

            def messages(self):
                return [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user",   "content": "What is 2+2?"},
                    {"role": "assistant", "content": "4"},
                ]
        """
        return []

    def schema(self) -> Optional[Type]:
        """
        Return a Pydantic model class for structured output, or None for plain text.

        The agent forces the LLM to return a valid instance of this model.
        Access it via response.json() or response.content (raw JSON string).

        Example::

            from pydantic import BaseModel

            class LeadSummary(BaseModel):
                name: str
                score: int

            def schema(self):
                return LeadSummary
        """
        return None

    def tools(self) -> list[Callable]:
        """
        Return a list of callable tools the agent may invoke.

        Each tool should have a docstring and type-annotated parameters.
        LangChain's StructuredTool.from_function() builds the schema automatically.

        Example::

            def tools(self):
                return [search_web, lookup_crm, send_email]
        """
        return []

    def middleware(self) -> list[Callable]:
        """
        Return middleware callables that wrap each LLM request.
        Each middleware receives (message, next) and must call next(message).

        Example::

            def rate_limit(message, next):
                time.sleep(0.5)
                return next(message)

            def middleware(self):
                return [rate_limit]
        """
        return []

    def provider_options(self) -> dict:
        """
        Return provider-specific options keyed by provider name.
        Passed as model_kwargs to the LangChain chat model constructor.

        Example::

            def provider_options(self):
                return {
                    "anthropic": {
                        "thinking": {"type": "enabled", "budget_tokens": 1024},
                    },
                    "openai": {
                        "frequency_penalty": 0.5,
                    },
                }
        """
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
        """
        Send a prompt and return an AgentResponse.

        Runs the full agentic loop: if the model calls tools, they are
        executed and results fed back until the model stops or _max_steps
        is reached.

        Args:
            message:          The user message.
            system:           Override the system prompt for this call only.
            model:            Override the model for this call only.
            messages:         Extra conversation history to prepend.
            attachments:      Documents to include with the message.
            provider_options: Per-provider options merged for this call only.
        """
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
        """
        Stream a response token by token.

        Note: tool execution is not supported during streaming.
        Use prompt() for agentic tool loops.

        Example::

            for chunk in agent.stream("Write a report..."):
                print(chunk, end="", flush=True)
        """
        message = self.before(message)
        self._log_call("stream", message)
        yield from self._stream(message, system=system, model=model, provider_options=provider_options)

    def fake(self, patterns: dict[str, AgentResponse | AgentSnapshot]) -> "Agent":
        """
        Register fake responses for testing. Keys are glob patterns matched
        against the prompt text (case-insensitive glob).

        - ``AgentResponse`` — always returned as-is (fully offline).
        - ``AgentSnapshot`` — replayed from disk if the file exists; otherwise
          the real API is called, the response is saved, and replayed next time.

        Example::

            agent.fake({
                "*hello*":   AgentResponse(content="Hello!"),
                "*analyze*": AgentSnapshot(path="tests/fixtures/analysis.json"),
            })
        """
        for pattern, value in patterns.items():
            self._fakes[pattern] = value  # snapshots are stored un-resolved
        return self

    def assert_prompted(self, times: int | None = None) -> None:
        """
        Assert that prompt() or stream() was called.

        Args:
            times: If given, assert exactly this many calls. Otherwise assert >= 1.
        """
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

    def _apply_middleware(
        self, message: str, final: Callable[[str], AgentResponse]
    ) -> AgentResponse:
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

    def _tools_schema(self) -> list[dict]:
        """Convert tools() callables to Anthropic-style tool definitions."""
        import inspect
        result = []
        for tool in self.tools():
            if not callable(tool):
                continue
            sig = inspect.signature(tool)
            try:
                import typing
                hints = typing.get_type_hints(tool)
            except Exception:
                hints = {}
            properties = {
                name: {"type": _python_type_to_json(hints.get(name, str))}
                for name in sig.parameters
            }
            result.append({
                "name": tool.__name__,
                "description": inspect.getdoc(tool) or tool.__name__,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": [
                        n for n, p in sig.parameters.items()
                        if p.default is inspect.Parameter.empty
                    ],
                },
            })
        return result

    # ── Provider dispatch ───────────────────────────────────────────────────

    def _run(
        self,
        message: str,
        system: str | None,
        model: str | None,
        extra_messages: list[dict] | None,
        attachments: list[Document] | None,
        provider_options: dict | None,
    ) -> AgentResponse:
        resolved_system, messages = self._build_messages(message, system, extra_messages, attachments)
        resolved_model = self._resolve_model(model)
        options = self._get_provider_options(provider_options)

        if self._provider == "anthropic":
            return self._run_anthropic(resolved_system, messages, resolved_model, options)
        if self._provider == "openai":
            return self._run_openai(resolved_system, messages, resolved_model, options)
        raise ValueError(f"Unsupported provider: {self._provider!r}. Use 'anthropic' or 'openai'.")

    def _stream(
        self,
        message: str,
        system: str | None,
        model: str | None,
        provider_options: dict | None,
    ) -> Iterator[str]:
        resolved_system, messages = self._build_messages(message, system)
        resolved_model = self._resolve_model(model)
        options = self._get_provider_options(provider_options)

        if self._provider == "anthropic":
            yield from self._stream_anthropic(resolved_system, messages, resolved_model, options)
        elif self._provider == "openai":
            yield from self._stream_openai(resolved_system, messages, resolved_model, options)
        else:
            raise ValueError(f"Unsupported provider: {self._provider!r}. Use 'anthropic' or 'openai'.")

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
        tools_schema = self._tools_schema()
        if tools_schema:
            params["tools"] = tools_schema

        # Agentic tool loop
        for _step in range(self._max_steps):
            resp = client.messages.create(**params)

            if resp.stop_reason != "tool_use":
                break

            # Collect tool calls and execute them
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            tool_results = []
            for tu in tool_uses:
                try:
                    result = self._execute_tool(tu.name, tu.input)
                except Exception as exc:
                    result = f"Error: {exc}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": str(result),
                })

            # Feed results back into the conversation
            params["messages"] = [
                *params["messages"],
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": tool_results},
            ]

        content = "".join(
            b.text for b in resp.content if hasattr(b, "text")
        )
        tool_calls = [
            {"name": b.name, "input": b.input}
            for b in resp.content if b.type == "tool_use"
        ]
        return AgentResponse(
            content=content,
            tool_calls=tool_calls,
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
