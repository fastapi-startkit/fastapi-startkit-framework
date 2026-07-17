from __future__ import annotations

import functools
import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .model_builder import ModelBuilder

if TYPE_CHECKING:
    from .agent import Agent


def _joined(value: Any) -> str:
    """A cassette value is a buffered string or a list of stream chunks."""
    return "".join(value) if isinstance(value, list) else value


def _text(content: Any) -> str:
    return content if isinstance(content, str) else str(content)


class RecordingModel:
    """A chat-model stand-in that replays a cassette or, on a miss, calls the
    real model once and records the response for future runs."""

    def __init__(self, agent: Agent, cassette: Path, initial_messages: list | None = None) -> None:
        self._agent = agent
        self._cassette = cassette
        self._initial = list(initial_messages or [])

    def bind_tools(self, tools: Any, **kwargs: Any) -> RecordingModel:
        return self

    def _real(self) -> Any:
        return ModelBuilder(agent=self._agent).build()

    def _prepared(self, messages: Any) -> list:
        return self._initial + list(messages)

    @staticmethod
    def _key(messages: list) -> str:
        payload = json.dumps(messages, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _load(self) -> dict:
        return json.loads(self._cassette.read_text()) if self._cassette.exists() else {}

    def _save(self, store: dict, key: str, value: Any) -> None:
        store[key] = value
        self._cassette.parent.mkdir(parents=True, exist_ok=True)
        self._cassette.write_text(json.dumps(store, indent=2, sort_keys=True))

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        from langchain_core.messages import AIMessage  # noqa: PLC0415

        prepared = self._prepared(messages)
        store = self._load()
        key = self._key(prepared)
        if key in store:
            return AIMessage(content=_joined(store[key]))

        response = await self._real().ainvoke(prepared)
        self._save(store, key, _text(response.content))
        return response

    async def astream(self, messages: Any, **kwargs: Any) -> Any:
        from langchain_core.messages import AIMessageChunk  # noqa: PLC0415

        prepared = self._prepared(messages)
        store = self._load()
        key = self._key(prepared)
        if key in store:
            value = store[key]
            for chunk in value if isinstance(value, list) else [value]:
                yield AIMessageChunk(content=chunk)
            return

        chunks: list[str] = []
        async for chunk in self._real().astream(prepared):
            chunks.append(_text(chunk.content))
            yield chunk
        self._save(store, key, chunks)


class _ModelSwap:
    """Registers a model stand-in for an agent class for the duration of a
    ``with`` block (or a decorated function) — the agent itself is untouched, so
    its real pipeline runs and only the model is swapped."""

    _agent_cls: type[Agent]

    def _build_model(self) -> Any:
        raise NotImplementedError

    def __enter__(self) -> Any:
        model = self._build_model()
        ModelBuilder.register_fake(self._agent_cls, model)
        return model

    def __exit__(self, *_exc: Any) -> bool:
        ModelBuilder.clear_fake(self._agent_cls)
        return False

    def __call__(self, func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                with self:
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        return wrapper


class AgentFake(_ModelSwap):
    """Swaps the agent's model for one that replays ``responses`` in order."""

    def __init__(self, agent_cls: type[Agent], responses: list) -> None:
        self._agent_cls = agent_cls
        self._responses = responses

    def _build_model(self) -> Any:
        from .fakes import fake_chat_model  # noqa: PLC0415

        return fake_chat_model(self._responses)


class AgentRecordFake(_ModelSwap):
    """Swaps the agent's model for a record-and-replay model backed by a cassette."""

    def __init__(self, agent: Agent, cassette: str | None = None, messages: list | None = None) -> None:
        self._agent = agent
        self._agent_cls = type(agent)
        self._cassette: Path | None = Path(cassette) if cassette else None
        self._messages = messages

    def _resolve_cassette(self, filename: str, qualname: str) -> None:
        here = Path(filename).parent
        if self._cassette is None:
            self._cassette = here / "cassettes" / f"{qualname.replace('.', '_')}.json"
        elif not self._cassette.is_absolute():
            self._cassette = here / self._cassette

    def _build_model(self) -> Any:
        assert self._cassette is not None, "RecordingModel has no cassette resolved"
        return RecordingModel(self._agent, self._cassette, self._messages)

    def __enter__(self) -> Any:
        caller = sys._getframe(1).f_code
        self._resolve_cassette(caller.co_filename, caller.co_qualname)
        return super().__enter__()

    def __call__(self, func: Callable) -> Callable:
        self._resolve_cassette(inspect.getfile(func), func.__qualname__)
        return super().__call__(func)
