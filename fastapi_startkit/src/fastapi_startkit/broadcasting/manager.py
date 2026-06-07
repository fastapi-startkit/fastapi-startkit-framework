class BroadcastManager:
    def __init__(self, config, server=None):
        self._config = config
        self._server = server

    def driver(self, name=None):
        name = name or self._config.get("default", "log")
        if name == "log":
            from .drivers.log_driver import LogDriver

            return LogDriver()
        elif name == "reverb":
            from .drivers.reverb_driver import ReverbDriver

            return ReverbDriver(self._server)
        raise ValueError(f"Unknown broadcast driver: {name}")

    async def event(self, broadcast_event) -> None:
        await self.driver().broadcast(broadcast_event)
