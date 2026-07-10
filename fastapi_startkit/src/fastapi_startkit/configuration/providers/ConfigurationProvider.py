from fastapi_startkit.support import Provider

from ..Configuration import Configuration


class ConfigurationProvider(Provider):
    def register(self):
        config = Configuration(self.app)
        # config.load()
        self.app.bind("config", config)

    def boot(self):
        pass
