from ..application import app


async def broadcast(event) -> None:
    """Broadcast an event using the default driver."""
    manager = app().make("broadcasting")
    await manager.event(event)
