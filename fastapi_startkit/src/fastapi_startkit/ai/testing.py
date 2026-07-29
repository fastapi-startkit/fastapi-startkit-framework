from __future__ import annotations

import functools
import hashlib
import inspect
import json
import operator
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from . import recording
from . import state as agent_state

if TYPE_CHECKING:
    from .agent import Agent
    from .document import Document


def _joined(value: Any) -> str:
    return "".join(value) if isinstance(value, list) else value


def _frame_text(frame: Any) -> str:
    """Text carried by a stream event; cassettes keep storing plain strings."""
    if isinstance(frame, dict):
        if frame.get("event") == "on_chat_model_stream":
            chunk = (frame.get("data") or {}).get("chunk")
            text = getattr(chunk, "content", "") or ""
            return text if isinstance(text, str) else str(text)
        if "event" in frame:  # start/end events carry no streamable text
            return ""
        return frame.get("text") or frame.get("content") or ""  # legacy frames
    return str(frame)


def _chunk_event(text: str) -> dict:
    """A replayed on_chat_model_stream event, shaped like astream_events yields."""
    from langchain_core.messages import AIMessageChunk  # noqa: PLC0415

    return {
        "event": "on_chat_model_stream",
        "name": "replay",
        "run_id": "",
        "tags": [],
        "metadata": {},
        "parent_ids": [],
        "data": {"chunk": AIMessageChunk(content=text)},
    }


def _new_token_totals() -> dict:
    return {"input": 0, "output": 0, "cache": 0, "total": 0}


def _text_state(content: str, tool_calls: list | None = None) -> dict:
    """A minimal one-message state for legacy/fallback shapes."""
    from langchain_core.messages import AIMessage  # noqa: PLC0415

    return {"messages": [AIMessage(content=content, tool_calls=tool_calls or [])]}


class TokenQuery:
    """Fluent predicate over accumulated token totals, e.g.::

        agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))

    Fields: ``input`` / ``output`` / ``cache`` / ``total``.
    """

    _OPS = {
        "<=": operator.le,
        ">=": operator.ge,
        "<": operator.lt,
        ">": operator.gt,
        "==": operator.eq,
        "=": operator.eq,
        "!=": operator.ne,
    }

    def __init__(self, totals: dict) -> None:
        self._totals = totals
        self._checks: list[tuple[str, str, float]] = []

    def where(self, field: str, op: str, value: float) -> "TokenQuery":
        self._checks.append((field, op, value))
        return self

    def failures(self) -> list[str]:
        problems: list[str] = []
        for field, op, value in self._checks:
            compare = self._OPS.get(op)
            if compare is None:
                raise ValueError(f"Unsupported token operator {op!r}")
            actual = self._totals.get(field, 0)
            if not compare(actual, value):
                problems.append(f"{field}={actual} is not {op} {value}")
        return problems


class AgentFake:
    def __init__(self, agent_cls: type[Agent], responses: list) -> None:
        self._agent_cls = agent_cls
        self._responses = list(responses)
        self._agent = agent_cls()
        self._agent.messages = self._history  # type: ignore[method-assign]
        self._records: list[dict] = []
        self._last_response: dict | None = None
        self.last_elapsed: float | None = None
        self._tokens: dict = _new_token_totals()
        self._response_time: float = 0.0

    def _history(self) -> list:
        return self._records

    @property
    def _prompts(self) -> list[str]:
        return [r["content"] for r in self._records if r.get("role") == "user"]

    def __enter__(self) -> "AgentFake":
        from .ai import Ai

        Ai.fake(self._agent_cls.__name__, self._responses)
        return self

    def __exit__(self, *_exc: Any) -> bool:
        from .ai import Ai

        Ai.forget(self._agent_cls.__name__)
        return False

    async def prompt(
        self, message: str, *, attachments: list[Document] | None = None, config: dict | None = None
    ) -> dict:
        start = time.monotonic()
        extra = {"config": config} if config is not None else {}
        self._last_response = await self._agent.prompt(message, attachments=attachments, **extra)
        self.last_elapsed = time.monotonic() - start
        self._remember(message, self._last_response)
        return self._last_response

    async def stream(self, message: str, *, config: dict | None = None) -> AsyncIterator[dict]:
        chunks: list[str] = []
        extra = {"config": config} if config is not None else {}
        # Drive the runner directly so we can read the structured response it
        # captures while streaming (content + tool_calls), not just joined text.
        runner = self._agent.runner()
        async for frame in runner.stream(message, **extra):
            if text := _frame_text(frame):
                chunks.append(text)
            yield frame
        self._last_response = getattr(runner, "last_response", None) or _text_state("".join(chunks))
        self._remember(message, self._last_response)

    def _remember(self, message: str, state: dict) -> None:
        self._accumulate_tokens(state)
        self._response_time += agent_state.runtime(state)
        self._records.append({"role": "user", "content": message})
        self._records.append({"role": "assistant", "content": agent_state.text(state)})

    def _accumulate_tokens(self, state: dict) -> None:
        """Add a turn's token usage — read from each AI message's usage_metadata —
        to the running totals."""
        recording.accumulate_uses(agent_state.messages(state), self._tokens)

    def assert_tokens(self, predicate: Callable[[TokenQuery], Any]) -> None:
        """Assert on the tokens accumulated across every prompt()/stream() so far.

        agent.assert_tokens(lambda x: x.where("input", "<=", 5000).where("output", "<=", 5000))
        """
        query = TokenQuery(dict(self._tokens))
        predicate(query)
        failures = query.failures()
        assert not failures, f"Token assertion failed: {'; '.join(failures)}. Accumulated tokens: {self._tokens}"

    def assert_prompt(self, expected: str | Callable[[str], bool]) -> None:
        if callable(expected):
            assert any(expected(p) for p in self._prompts), (
                f"No recorded prompt satisfied the predicate. Got: {self._prompts!r}"
            )
        else:
            assert any(expected in p for p in self._prompts), (
                f"Expected a prompt containing {expected!r}, but none did. Got: {self._prompts!r}"
            )

    def assert_response(self, expected: str) -> None:
        content = agent_state.text(self._require_response())
        assert expected in content, f"Expected response to contain {expected!r}, got {content!r}"

    def assert_tool_call(self, name: str) -> None:
        called = [tc.get("name") for tc in agent_state.tool_calls(self._require_response())]
        assert name in called, f"Expected tool {name!r} to be called, but got: {called}"

    def assert_prompted(self, times: int | None = None) -> None:
        if times is not None:
            assert len(self._prompts) == times, f"Expected {times} prompt call(s), got {len(self._prompts)}"
        else:
            assert self._prompts, "Expected at least one prompt() or stream() call, but none were made"

    def assert_not_prompted(self) -> None:
        self.assert_prompted(times=0)

    def reset(self) -> "AgentFake":
        self._records.clear()
        self._last_response = None
        self._tokens = _new_token_totals()
        self._response_time = 0.0
        return self

    def _require_response(self) -> dict:
        assert self._last_response is not None, "No prompt() call has been made yet."
        return self._last_response

    def _tool_call_names(self) -> list[str]:
        return [tc.get("name", "") for tc in agent_state.tool_calls(self._require_response())]

    def assert_text_response(self) -> None:
        assert agent_state.text(self._require_response()), (
            "Expected a non-empty text response, but content was empty."
        )

    def assert_tool_called(self, name: str, predicate: Callable[[AssertToolCall], bool] | None = None) -> None:
        matches = [tc for tc in agent_state.tool_calls(self._require_response()) if tc.get("name") == name]
        assert matches, f"Expected tool {name!r} to be called, but it wasn't. Called: {self._tool_call_names()}"
        if predicate is not None:
            assert any(predicate(AssertToolCall(tc)) for tc in matches), (
                f"Tool {name!r} was called, but no call satisfied the given predicate."
            )

    def assert_tool_not_called(self, names: list[str]) -> None:
        unexpected = set(self._tool_call_names()) & set(names)
        assert not unexpected, f"Expected tools {sorted(names)} not to be called, but got: {sorted(unexpected)}"

    def assert_response_time_lt(self, seconds: float) -> None:
        """Assert on the response time accumulated across every prompt()/stream() so far.

        The time is read from the recorded transcript (each ai/tool step's
        ``response_time``), not the wall-clock duration of the call — so it stays
        correct on cassette replay, where the cache read is effectively instant.
        """
        assert self.last_elapsed is not None, "No prompt() call has been made yet."
        total = self._response_time
        assert total < seconds, f"Expected total response time < {seconds}s, took {total:.3f}s"

    async def assert_response_judged(self, *, model: str, expectation: str, provider: str | None = None) -> None:
        content = agent_state.text(self._require_response())
        verdict = await self._judge(model, expectation, content, provider)
        assert verdict.get("passed"), (
            f"Judge ({model}) rejected the response for expectation {expectation!r}: "
            f"{verdict.get('reasoning', '')!r} — response was {content!r}"
        )

    async def _judge(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        return await self._judge_live(model, expectation, content, provider)

    async def _judge_live(self, model: str, expectation: str, content: str, provider: str | None = None) -> dict:
        from .judge import JudgeAgent  # noqa: PLC0415

        judge = JudgeAgent()
        judge.model = model
        judge.provider = provider
        return await judge.judge(expectation, content)

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


class AssertToolCall:
    def __init__(self, data: dict) -> None:
        self.name = data.get("name", "")
        self.args = data.get("args") or {}
        self.id = data.get("id")
        self._data = data

    def __repr__(self) -> str:
        return f"AssertToolCall(name={self.name!r}, args={self.args!r})"


class AgentRecordFake(AgentFake):
    def __init__(self, real: Agent, cassette: str | None = None, messages: list | None = None) -> None:
        self._real = real
        self.cassette: Path | None = Path(cassette) if cassette else None
        self._seed_messages: list = list(messages or [])
        self._records: list[dict] = []
        self._real.messages = self._history  # type: ignore[method-assign]
        self._last_response: dict | None = None
        self.last_elapsed: float | None = None
        self._tokens: dict = _new_token_totals()
        self._response_time: float = 0.0

    def _history(self) -> list:
        return self._seed_messages + self._records

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
        assert cassette is not None, "AgentRecordFake has no cassette resolved"
        return cassette, (json.loads(cassette.read_text()) if cassette.exists() else {})

    def _save(self, cassette: Path, store: dict, key: str, value: Any) -> None:
        store[key] = value
        cassette.parent.mkdir(parents=True, exist_ok=True)
        cassette.write_text(json.dumps(store, indent=2, sort_keys=True))

    def _turn(self, message: str, state: dict, chunks: list[str] | None = None) -> list[dict]:
        """Build the ordered per-turn transcript persisted to the cassette:
        the human input followed by the turn's AI/tool messages. Streamed
        ``chunks`` are attached to the last model entry so replay can re-emit
        them."""
        entries: list[dict] = [recording.human(message)]
        entries.extend(recording.entries_from_messages(agent_state.messages(state)))
        if chunks:
            for entry in reversed(entries):
                if entry["type"] == "ai":
                    entry["chunks"] = chunks
                    break
        return entries

    @staticmethod
    def _state_from_cache(value: Any) -> dict:
        if recording.is_transcript(value):
            return recording.to_state(value)
        if isinstance(value, dict) and "content" in value:  # legacy flat shape
            return _text_state(_joined(value.get("content", "")), value.get("tool_calls") or [])
        return _text_state(_joined(value))

    def _remember_turn(self, message: str, state: dict) -> None:
        self._accumulate_tokens(state)
        self._response_time += agent_state.runtime(state)
        self._records.append({"role": "user", "content": message})
        turn: dict[str, Any] = {"role": "assistant", "content": agent_state.text(state)}
        if agent_state.tool_calls(state):
            turn["tool_calls"] = agent_state.tool_calls(state)
        self._records.append(turn)

    async def prompt(
        self, message: str, *, attachments: list[Document] | None = None, config: dict | None = None
    ) -> dict:
        cassette, store = self._load()
        key = self._key(message, attachments)
        start = time.monotonic()
        if key in store:
            state = self._state_from_cache(store[key])
        else:
            extra = {"config": config} if config is not None else {}
            state = await self._real.prompt(message, attachments=attachments, **extra)
            self._save(cassette, store, key, self._turn(message, state))
        state = self._real.runner()._apply_schema(state)
        self.last_elapsed = time.monotonic() - start
        self._last_response = state
        self._remember_turn(message, state)
        return state

    async def stream(self, message: str, *, config: dict | None = None) -> AsyncIterator[dict]:
        cassette, store = self._load()
        key = self._key(message, None)
        if key in store:
            value = store[key]
            if recording.is_transcript(value):
                chunks = recording.chunks_from_transcript(value)
                state = self._state_from_cache(value)
            elif isinstance(value, dict):  # legacy flat shape with buffered chunks
                chunks = value.get("chunks", [])
                state = self._state_from_cache(value)
            else:  # legacy cassette: a bare list of text chunks
                chunks = value if isinstance(value, list) else [value]
                state = _text_state(_joined(chunks))
            for chunk in chunks:
                yield _chunk_event(chunk)
        else:
            extra = {"config": config} if config is not None else {}
            # Drive the runner directly to capture the structured state
            # (messages + chunks) it records while streaming.
            runner = self._real.runner()
            chunks = []
            async for frame in runner.stream(message, **extra):
                if text := _frame_text(frame):
                    chunks.append(text)
                yield frame
            state = getattr(runner, "last_response", None) or _text_state(_joined(chunks))
            self._save(cassette, store, key, self._turn(message, state, chunks=chunks))
        self._last_response = state
        self._remember_turn(message, state)

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

    def _resolve_cassette(self, filename: str, qualname: str) -> None:
        here = Path(filename).parent
        if self.cassette is None:
            self.cassette = here / "cassettes" / f"{qualname.replace('.', '_')}.json"
        elif not self.cassette.is_absolute():
            self.cassette = here / self.cassette

    def __enter__(self) -> "AgentRecordFake":
        caller = sys._getframe(1).f_code
        self._resolve_cassette(caller.co_filename, caller.co_qualname)
        return self

    def __exit__(self, *_exc: Any) -> bool:
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
