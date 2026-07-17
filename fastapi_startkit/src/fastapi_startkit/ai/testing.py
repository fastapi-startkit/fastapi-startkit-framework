from __future__ import annotations

import fnmatch
import functools
import hashlib
import inspect
import json
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .response import AgentResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


def _matches(pattern: str, message: str) -> bool:
    pattern, message = pattern.lower(), message.lower()
    if any(ch in pattern for ch in "*?["):
        return fnmatch.fnmatch(message, pattern)
    return pattern in message


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.attachments: list[list[Document]] = []

    def _record_call(self, message: str, attachments: list[Document] | None) -> None:
        self.calls.append(message)
        self.attachments.append(list(attachments or []))

    @property
    def prompt_count(self) -> int:
        return len(self.calls)

    def assert_prompted(self, pattern: str | None = None) -> None:
        if pattern is None:
            assert self.calls, "Expected the agent to be prompted, but it never was."
            return
        assert any(_matches(pattern, message) for message in self.calls), (
            f"Expected a prompt matching {pattern!r}, but none did. Got: {self.calls!r}"
        )

    def assert_not_prompted(self) -> None:
        assert not self.calls, f"Expected no prompts, but got: {self.calls!r}"


def _joined(value: Any) -> str:
    """A cassette value is a buffered string or a list of stream chunks."""
    return "".join(value) if isinstance(value, list) else value


class AgentModelFake:
    """Registers a fixed, ordered list of replies as ``agent_cls``'s chat
    model for the duration of a ``with`` block (or a decorated function).

    Unlike the old pattern-matching stand-in, this swaps only the model —
    ``prompt()``/``stream()`` still run the real message-building, pipeline,
    and tool-execution path; see ``Ai.fake()``.
    """

    def __init__(self, agent_cls: type[Agent], responses: list) -> None:
        self._agent_cls = agent_cls
        self._responses = responses

    def __enter__(self) -> None:
        from .ai import Ai

        Ai.fake(self._agent_cls.__name__, self._responses)

    def __exit__(self, *_exc: Any) -> bool:
        from .ai import Ai

        Ai.forget(self._agent_cls.__name__)
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


class ToolCallView:
    """Ergonomic, attribute-style view of a raw ``tool_calls`` dict, passed
    to ``assert_tool_called``'s predicate."""

    def __init__(self, data: dict) -> None:
        self.name = data.get("name", "")
        self.args = data.get("args") or {}
        self.id = data.get("id")
        self._data = data

    def __repr__(self) -> str:
        return f"ToolCallView(name={self.name!r}, args={self.args!r})"


class RecordingAgent(_Recorder):
    """Bound as ``agent`` by ``with Agent.record(cassette) as agent:``.

    Fluent testing handle around a record-and-replay session: ``prompt()``
    is async (it's the same real agent call underneath, just cached) and
    each call mutates the handle's "current turn" state, which the
    ``assert_*`` methods judge against — mirroring how a browser-testing
    ``page`` object exposes assertions against the current page state.

    On a cassette miss, the real agent is called once and the response is
    cached to disk (keyed by the conversation history so far, plus the new
    message, so two sessions with different histories but the same latest
    message text don't collide). On a hit, it's replayed with no live call.
    """

    def __init__(self, real: Agent, cassette: str | None = None, messages: list | None = None) -> None:
        super().__init__()
        self._real = real
        self.cassette: Path | None = Path(cassette) if cassette else None
        self._seed_messages: list = list(messages or [])
        self._transcript: list[dict] = []
        self._real.messages = self._history  # type: ignore[method-assign]
        self.last_response: AgentResponse | None = None
        self.last_elapsed: float | None = None

    def _history(self) -> list:
        return self._seed_messages + self._transcript

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, dict):
            return value
        return {"type": type(value).__name__, "content": getattr(value, "content", str(value))}

    def _key(self, message: str, attachments: list[Document] | None) -> str:
        names = [getattr(doc, "name", "") for doc in (attachments or [])]
        payload = json.dumps(
            {
                "history": [self._serialize(m) for m in self._history()],
                "message": message,
                "attachments": names,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _load(self) -> tuple[Path, dict]:
        cassette = self.cassette
        assert cassette is not None, "RecordingAgent has no cassette resolved"
        return cassette, (json.loads(cassette.read_text()) if cassette.exists() else {})

    def _save(self, cassette: Path, store: dict, key: str, value: Any) -> None:
        store[key] = value
        cassette.parent.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps(store, indent=2, sort_keys=True))

    @staticmethod
    def _cache_prompt_value(response: AgentResponse) -> dict:
        return {"content": response.content, "tool_calls": response.tool_calls}

    @staticmethod
    def _response_from_cache(value: Any) -> AgentResponse:
        if isinstance(value, dict) and "content" in value:
            return AgentResponse(content=_joined(value.get("content", "")), tool_calls=value.get("tool_calls") or [])
        return AgentResponse(content=_joined(value))

    def _remember_turn(self, message: str, response: AgentResponse) -> None:
        self._transcript.append({"role": "user", "content": message})
        turn: dict[str, Any] = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            turn["tool_calls"] = response.tool_calls
        self._transcript.append(turn)

    async def prompt(self, message: str, *, attachments: list[Document] | None = None) -> AgentResponse:
        """Run (or replay) one turn and make it the "current" response that
        assert_*() methods judge."""
        self._record_call(message, attachments)
        cassette, store = self._load()
        key = self._key(message, attachments)
        start = time.monotonic()
        if key in store:
            response = self._response_from_cache(store[key])
        else:
            response = await self._real._run(message, attachments=attachments)
            self._save(cassette, store, key, self._cache_prompt_value(response))
        self.last_elapsed = time.monotonic() - start
        self.last_response = response
        self._remember_turn(message, response)
        return response

    async def stream(self, message: str) -> AsyncIterator[str]:
        self._record_call(message, None)
        cassette, store = self._load()
        key = self._key(message, None)
        if key in store:
            value = store[key]
            for chunk in value if isinstance(value, list) else [value]:
                yield chunk
            return
        chunks = [chunk async for chunk in self._real._stream(message)]
        self._save(cassette, store, key, chunks)
        for chunk in chunks:
            yield chunk

    def _require_response(self) -> AgentResponse:
        assert self.last_response is not None, "No prompt() call has been made yet."
        return self.last_response

    def _tool_call_names(self) -> list[str]:
        return [tc.get("name", "") for tc in self._require_response().tool_calls]

    def assert_text_response(self) -> None:
        response = self._require_response()
        assert response.content, "Expected a non-empty text response, but content was empty."

    def assert_tool_called(self, name: str, predicate: Callable[[ToolCallView], bool] | None = None) -> None:
        response = self._require_response()
        matches = [tc for tc in response.tool_calls if tc.get("name") == name]
        assert matches, f"Expected tool {name!r} to be called, but it wasn't. Called: {self._tool_call_names()}"
        if predicate is not None:
            assert any(predicate(ToolCallView(tc)) for tc in matches), (
                f"Tool {name!r} was called, but no call satisfied the given predicate."
            )

    def assert_tool_not_called(self, names: list[str]) -> None:
        unexpected = set(self._tool_call_names()) & set(names)
        assert not unexpected, f"Expected tools {sorted(names)} not to be called, but got: {sorted(unexpected)}"

    def assert_response_time_lt(self, seconds: float) -> None:
        assert self.last_elapsed is not None, "No prompt() call has been made yet."
        assert self.last_elapsed < seconds, f"Expected response time < {seconds}s, took {self.last_elapsed:.3f}s"

    async def assert_response_judged(self, *, model: str, expectation: str, provider: str | None = None) -> None:
        response = self._require_response()
        verdict = await self._judge(model, expectation, response.content, provider)
        assert verdict.get("passed"), (
            f"Judge ({model}) rejected the response for expectation {expectation!r}: "
            f"{verdict.get('reasoning', '')!r} — response was {response.content!r}"
        )

    async def _judge(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        cassette, store = self._load()
        key = self._judge_key(model, expectation, content, provider)
        if key in store:
            return store[key]
        verdict = await self._judge_live(model, expectation, content, provider)
        self._save(cassette, store, key, verdict)
        return verdict

    @staticmethod
    def _judge_key(model: str, expectation: str, content: str, provider: str | None = None) -> str:
        payload = json.dumps(
            {"judge_model": model, "judge_provider": provider, "expectation": expectation, "content": content},
            sort_keys=True,
        )
        return "judge:" + hashlib.sha256(payload.encode()).hexdigest()

    async def _judge_live(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        from .judge import JudgeAgent  # noqa: PLC0415

        judge = JudgeAgent()
        judge.model = model
        judge.provider = provider
        return await judge.judge(expectation, content)


class AgentBinding:
    def __init__(self, agent_cls: type[Agent], stand_in: Any) -> None:
        self._agent_cls = agent_cls
        self._stand_in = stand_in

    def _resolve_cassette(self, filename: str, qualname: str) -> None:
        stand_in = self._stand_in
        if not isinstance(stand_in, RecordingAgent):
            return
        here = Path(filename).parent
        if stand_in.cassette is None:
            stand_in.cassette = here / "cassettes" / f"{qualname.replace('.', '_')}.json"
        elif not stand_in.cassette.is_absolute():
            stand_in.cassette = here / stand_in.cassette

    def __enter__(self) -> Any:
        from fastapi_startkit.application import app

        caller = sys._getframe(1).f_code
        self._resolve_cassette(caller.co_filename, caller.co_qualname)
        app().bind(self._agent_cls.__name__, self._stand_in)
        return self._stand_in

    def __exit__(self, *_exc: Any) -> bool:
        from fastapi_startkit.application import app

        app().unbind(self._agent_cls.__name__)
        return False

    def __call__(self, func: Callable) -> Callable:
        self._resolve_cassette(inspect.getfile(func), func.__qualname__)

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
