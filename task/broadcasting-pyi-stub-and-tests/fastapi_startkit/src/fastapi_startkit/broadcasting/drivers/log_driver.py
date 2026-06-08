import logging

logger = logging.getLogger("reverb")


class LogDriver:
    async def broadcast(self, event) -> None:
        for channel in event.broadcast_on():
            logger.info(
                f"[Broadcast] channel={channel.name} event={event.broadcast_as()} data={event.broadcast_with()}"
            )
