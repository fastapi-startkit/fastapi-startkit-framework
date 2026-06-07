class ReverbDriver:
    def __init__(self, server):
        self.server = server

    async def broadcast(self, event) -> None:
        for channel in event.broadcast_on():
            await self.server.broadcast_to_channel(
                channel.name, event.broadcast_as(), event.broadcast_with()
            )
