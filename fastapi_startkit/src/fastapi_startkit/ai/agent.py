from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any, AsyncIterator, Callable, Optional, Type

from .document import Document
from .response import AgentResponse, AgentSnapshot
from .testing import AgentBinding
from .transport import InlineFakeTransport, LiveTransport, StandInTransport, Transport

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool


class Agent:
    provider: str | None = None
    model: str | None = None
    max_steps: int = 10
    max_tokens: int = 4096
    timeout: float = 30.0
    top_p: float = 1.0

    def __init__(self):
        self._fakes: dict[str, AgentResponse | AgentSnapshot] = {}
        self._call_log: list[dict] = []

    def messages(self) -> list[dict]:
        return []

    def instructions(self) -> str | None:
        return None

    def schema(self) -> Optional[Type]:
        return None

    def tools(self) -> list[BaseTool]:
        return []

    def middleware(self) -> list[Callable]:
        return []

    def provider_options(self) -> dict:
        return {}

    async def prompt(
        self,
        message: str,
        *,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        response = await self._transport(message).prompt(
            message,
            model=model,
            attachments=attachments,
            provider_options=provider_options,
        )
        self._log_call("prompt", message)
        return self._apply_schema(response)

    async def stream(
        self,
        message: str,
        *,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[str]:
        self._log_call("stream", message)
        async for chunk in self._transport(message).stream(
            message,
            model=model,
            provider_options=provider_options,
        ):
            yield chunk

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

    def _transport(self, message: str) -> Transport:
        stand_in = self._faked()
        if stand_in is not None:
            return StandInTransport(self, stand_in)

        match = self._match_fake(message)
        if match is not None:
            return InlineFakeTransport(self, match)

        return LiveTransport(self)

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

    async def _run_pipeline(self, chat_model: Any, messages: list) -> AgentResponse:
        from .pipeline import Response, build_pipeline  # noqa: PLC0415
        from .runner import Runner  # noqa: PLC0415

        chain = list(self.middleware())
        if not chain:
            return await self._invoke(chat_model, messages)

        def core(model: Any) -> Response:
            async def _run():
                result = await Runner(self, model).run(messages)
                yield result

            return Response(_run)

        pipeline = build_pipeline(chain, core)
        raw = await pipeline(chat_model)
        return self._to_agent_response(raw)

    async def _apply_middleware(
        self,
        chat_model: Any,
        final: Callable[[Any], Any],
    ) -> AgentResponse:
        chain = list(self.middleware())

        def build(mw_list: list, fn: Callable) -> Callable:
            if not mw_list:
                return fn
            head, *tail = mw_list
            next_fn = build(tail, fn)
            mw = head() if isinstance(head, type) else head
            return lambda model: mw(model, next_fn)

        return await build(chain, final)(chat_model)

    def _build_instruction(self) -> str | None:
        return self.instructions()

    def _build_messages(
        self,
        message: str,
        attachments: list[Document] | None = None,
    ) -> list[dict]:
        messages: list[dict] = []

        instruction = self.instructions()
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
        from .model_builder import ModelBuilder  # noqa: PLC0415

        return ModelBuilder(agent=self).build(model, provider_options)

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

    def _apply_schema(self, response: AgentResponse) -> AgentResponse:
        schema = self.schema()
        if schema is not None and response.parsed is None and response.content:
            response.parsed = self._build_schema(schema, response.content)
        return response

    @staticmethod
    def _build_schema(schema: Any, content: str) -> Any:
        import json  # noqa: PLC0415

        if hasattr(schema, "model_validate_json"):
            return schema.model_validate_json(content)
        if hasattr(schema, "model_validate"):
            return schema.model_validate(json.loads(content))
        return schema(**json.loads(content))

    async def _invoke(self, chat_model: Any, messages: list[dict]) -> AgentResponse:
        from .runner import Runner  # noqa: PLC0415

        result = await Runner(self, chat_model).run(messages)
        return self._to_agent_response(result)

    async def _run(
        self,
        message: str,
        model: str | None = None,
        attachments: list[Document] | None = None,
        provider_options: dict | None = None,
    ) -> AgentResponse:
        messages = self._build_messages(message, attachments)
        chat_model = self._build_model(model, provider_options)
        return await self._invoke(chat_model, messages)

    async def _stream(
        self,
        message: str,
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> AsyncIterator[str]:
        from .pipeline import Response, build_pipeline  # noqa: PLC0415
        from .runner import StreamRunner  # noqa: PLC0415

        messages = self._build_messages(message)
        chat_model = self._build_model(model, provider_options)
        chain = list(self.middleware())

        def core(m: Any) -> Response:
            return Response(lambda: StreamRunner(self, m).run(messages))

        pipeline = build_pipeline(chain, core) if chain else core

        async for chunk in pipeline(chat_model):
            yield chunk
