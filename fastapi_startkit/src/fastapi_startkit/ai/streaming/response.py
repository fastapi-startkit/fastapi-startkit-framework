from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from .ag_ui import AgentUserInteractionProtocol
from .events import StreamEvent
from .normalizer import EventNormalizer
from .vercel import VercelDataProtocol

if TYPE_CHECKING:
    from starlette.responses import StreamingResponse

    from .protocol import StreamProtocol


class StreamableAgentResponse:
    def __init__(
        self,
        source: Callable[[], AsyncGenerator[dict[str, Any], None]],
        conversation_id: str | None = None,
    ) -> None:
        self._source = source
        self.invocation_id = str(uuid.uuid4())
        self.conversation_id = conversation_id

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return aiter(self._source())

    def events(self) -> AsyncGenerator[StreamEvent, None]:
        return EventNormalizer(self.invocation_id).normalize(self._source())

    def using_protocol(self, protocol: StreamProtocol) -> StreamingResponse:
        return protocol.response(self)

    def using_vercel_data_protocol(self) -> StreamingResponse:
        return self.using_protocol(VercelDataProtocol())

    def using_agent_user_interaction_protocol(
        self, thread_id: str | None = None, run_id: str | None = None
    ) -> StreamingResponse:
        return self.using_protocol(AgentUserInteractionProtocol(thread_id=thread_id, run_id=run_id))
