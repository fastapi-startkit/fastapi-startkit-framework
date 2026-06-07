from fastapi_startkit.broadcasting.channels import Channel
from fastapi_startkit.broadcasting.event import BroadcastEvent

class Broadcast:
    """Facade for broadcasting events over WebSocket channels."""

    @staticmethod
    async def event(event: BroadcastEvent) -> None:
        """Broadcast an event to all its channels."""
        ...

    @staticmethod
    def channel(name: str) -> Channel:
        """Return a Channel instance for the given name."""
        ...
