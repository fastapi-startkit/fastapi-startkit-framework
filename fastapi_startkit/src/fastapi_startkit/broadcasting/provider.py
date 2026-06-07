from ..providers import Provider
from .manager import BroadcastManager
from .config import BroadcastingConfig
from .reverb.server import ReverbServer


class ReverbProvider(Provider):
    provider_key = "broadcasting"

    def register(self) -> None:
        config_data = self.resolve_config(BroadcastingConfig)
        self.merge_config_from(config_data, "broadcasting")

        server = ReverbServer()
        manager = BroadcastManager(config_data, server)

        self.app.bind("broadcasting", manager)
        self.app.bind("reverb.server", server)

    def boot(self) -> None:
        pass
