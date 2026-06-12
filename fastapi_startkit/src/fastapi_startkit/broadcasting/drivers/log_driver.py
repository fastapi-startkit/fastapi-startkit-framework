import logging

logger = logging.getLogger("reverb")


class LogDriver:
    async def broadcast(self, event) -> None:
        for channel in event.broadcast_on():
            logger.info(
                f"[Broadcast] channel={channel.name} event={event.broadcast_as()} data={event.broadcast_with()}"
            )

    async def broadcast_raw(self, channel: str, event_name: str, payload: dict) -> None:
        """Log a raw channel/event/payload triple (used by :meth:`BroadcastManager.emit`)."""
        logger.info(f"[Broadcast] channel={channel} event={event_name} data={payload}")
