from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.responses import StreamingResponse

    from .response import StreamableAgentResponse


class StreamProtocol(ABC):
    media_type = "text/event-stream"

    def headers(self) -> dict[str, str]:
        return {"cache-control": "no-cache", "x-accel-buffering": "no"}

    @abstractmethod
    def encode(self, stream: StreamableAgentResponse) -> AsyncIterator[str]: ...

    @staticmethod
    def sse(payload: Any) -> str:
        data = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, default=str, ensure_ascii=False, separators=(",", ":"))
        )
        return "".join(f"data: {line}\n" for line in data.split("\n")) + "\n"

    def response(self, stream: StreamableAgentResponse) -> StreamingResponse:
        from starlette.responses import StreamingResponse

        return StreamingResponse(self.encode(stream), media_type=self.media_type, headers=self.headers())
