from __future__ import annotations

import fnmatch
from typing import Any, Callable, Iterator, Optional, Type

from .document import Document
from .lab import Lab
from .response import AgentResponse, AgentSnapshot
from .testing import AgentBinding


class Agent:
    _instructions: str | None = None
    _provider: str | None = None
    _model: str | None = None
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
        return None

    def tools(self) -> list[Callable]:
        return []

    def middleware(self) -> list[Callable]:
        return []

    def provider_options(self) -> dict:
        return {}

    def before(self, message: str) -> str:
        return message

    def after(self, response: AgentResponse) -> AgentResponse:
        return response

    def prompt(
            self,
            message: str,
            *,
            model: str | None = None,
            attachments: list[Document] | None = None,
            provider_options: dict | None = None,
    ) -> AgentResponse:
        message = self.before(message)

        stand_in = self._faked()
        if stand_in is not None:
            response = stand_in.prompt(message, attachments=attachments)
            self._log_call("prompt", message)
            return self.after(response)

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
        message = self.before(message)
        self._log_call("stream", message)

        swapped = self._faked()
        if swapped is not None:
            yield swapped.prompt(message).content
            return

        fake = self._match_fake(message)
        if fake is not None:
            if isinstance(fake, AgentSnapshot):
                response = fake.resolve(self, message)
            else:
                response = fake
            yield response.content
            return
        yield from self._stream(message, model=model, provider_options=provider_options)

    @classmethod
    def fake(cls, responses: dict | None = None) -> "AgentBinding":
        from .testing import AgentBinding, FakeAgent

        return AgentBinding(cls, FakeAgent(responses))

    @classmethod
    def record(cls, cassette: str | None = None) -> "AgentBinding":
        from .testing import AgentBinding, RecordingAgent

        return AgentBinding(cls, RecordingAgent(cls(), cassette))

    @classmethod
    def _binding(cls) -> Any:
        from fastapi_startkit.application import app

        container = app()
        return container.make(cls.__name__) if container.has(cls.__name__) else None

    @classmethod
    def make(cls) -> "Agent":
        binding = cls._binding()
        return binding if binding is not None else cls()

    def _faked(self) -> Any:
        binding = type(self)._binding()
        return binding if binding is not self else None

    def assert_prompted(self, times: int | None = None) -> None:
        calls = [c for c in self._call_log if c["method"] in ("prompt", "stream")]
        if times is not None:
            assert len(calls) == times, f"Expected {times} prompt call(s), got {len(calls)}"
        else:
            assert len(calls) > 0, "Expected at least one prompt() or stream() call, but none were made"

    def assert_not_prompted(self) -> None:
        self.assert_prompted(times=0)

    def reset(self) -> "Agent":
        self._fakes.clear()
        self._call_log.clear()
        return self

    def _match_fake(self, message: str) -> Optional[AgentResponse | AgentSnapshot]:
        for pattern, value in self._fakes.items():
            if fnmatch.fnmatch(message.lower(), pattern.lower()):
                return value
        return None

    def _log_call(self, method: str, message: str) -> None:
        self._call_log.append({"method": method, "message": message})

    def _apply_middleware(self, message: str, final: Callable[[str], AgentResponse]) -> AgentResponse:
        chain = list(self.middleware())

        def build(mw_list: list, fn: Callable) -> Callable:
            if not mw_list:
                return fn
            head, *tail = mw_list
            next_fn = build(tail, fn)
            return lambda msg: head(msg, next_fn)

        return build(chain, final)(message)

    def _resolve_model(self, override: str | None = None) -> str:
        return Lab.get_provider(self._provider).get_model(override or self._model or None)

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
        from langchain.chat_models import init_chat_model  # noqa: PLC0415

        lab = Lab.get_provider(self._provider)
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
