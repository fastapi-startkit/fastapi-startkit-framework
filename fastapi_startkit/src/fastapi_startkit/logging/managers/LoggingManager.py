from ..ChannelFactory import ChannelFactory
from ..factory import DriverFactory


class LoggingManager:
    def __init__(
        self,
        channel_factory: type[ChannelFactory] = ChannelFactory,
        driver_factory: type[DriverFactory] = DriverFactory,
    ):
        self.channel_factory = channel_factory
        self.driver_factory = driver_factory
        self.configure_python_logging()

    def channel(self, channel: str):
        channel_class = self.channel_factory.make(channel)
        if channel_class is None:
            raise ValueError(f"Logging channel '{channel}' is not registered.")
        return channel_class()

    @classmethod
    def configure_python_logging(cls):
        from ..handler import LoggingHandler

        LoggingHandler.install()
