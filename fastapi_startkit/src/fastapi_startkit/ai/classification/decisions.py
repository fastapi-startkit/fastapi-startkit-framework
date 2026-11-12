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

        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(DECISIONS_URL, json=payload, headers={"x-goog-api-key": self.api_key})
        except httpx.HTTPError as exc:
            raise ClassificationError(f"Decisions API request failed: {type(exc).__name__}: {exc}") from exc
        if response.is_error:
            raise ClassificationError(f"Decisions API request failed with {response.status_code}: {_error(response)}")
        try:
            body = response.json()
        except ValueError as exc:
            raise ClassificationError(
                f"Decisions API returned a response that is not JSON: {response.text[:200]!r}"
            ) from exc
        if not isinstance(body, dict):
            raise ClassificationError(f"Decisions API returned {type(body).__name__}, expected a JSON object.")
        return body

    @classmethod
    def fake(cls, responses: list[Payload] | DecisionsResponder) -> DecisionsFake:
        Decisions._faked = DecisionsFake(responses)
        return Decisions._faked

    @classmethod
    def reset_fake(cls) -> None:
        Decisions._faked = None


def _error(response: Any) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return response.text
    return f"{error.get('code', 'error')}: {error.get('message', '')}".rstrip(": ")
