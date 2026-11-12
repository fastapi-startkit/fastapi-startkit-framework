from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from .questions import ClassificationError

DECISIONS_URL = "https://generativelanguage.googleapis.com/v1beta/decisions"
DECISIONS_MODEL = "gemini-decision-1"

Payload = dict[str, Any]
DecisionsResponder = Callable[[Payload], Payload]


class DecisionsFake:
    def __init__(self, responses: list[Payload] | DecisionsResponder) -> None:
        self._responder = responses if callable(responses) else None
        self._queue = [] if callable(responses) else list(responses)
        self.requests: list[Payload] = []

    def respond(self, payload: Payload) -> Payload:
        self.requests.append(payload)
        if self._responder is not None:
            return self._responder(payload)
        if not self._queue:
            raise RuntimeError(f"No fake Decisions response left for questions {list(payload['questions'])}.")
        return self._queue.pop(0)


class Decisions:
    _faked: ClassVar[DecisionsFake | None] = None

    def __init__(self, api_key: str, timeout: float = 30.0, transport: Any = None) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport

    async def create(self, payload: Payload) -> Payload:
        if Decisions._faked is not None:
            return Decisions._faked.respond(payload)
        return await self._post(payload)

    async def _post(self, payload: Payload) -> Payload:
        import httpx  # noqa: PLC0415

        async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
            response = await client.post(DECISIONS_URL, json=payload, headers={"x-goog-api-key": self.api_key})
        if response.is_error:
            raise ClassificationError(f"Decisions API request failed with {response.status_code}: {_error(response)}")
        return response.json()

    @classmethod
    def fake(cls, responses: list[Payload] | DecisionsResponder) -> DecisionsFake:
        Decisions._faked = DecisionsFake(responses)
        return Decisions._faked

    @classmethod
    def reset_fake(cls) -> None:
        Decisions._faked = None


def _error(response: Any) -> str:
    try:
        error = response.json().get("error") or {}
    except ValueError:
        return response.text
    return f"{error.get('code', 'error')}: {error.get('message', '')}".rstrip(": ")
