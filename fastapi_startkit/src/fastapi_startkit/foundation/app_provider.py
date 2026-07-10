from fastapi_startkit.console.publish_command import PublishCommand
from fastapi_startkit.support import Provider


class AppProvider(Provider):
    def register(self) -> None:
        pass

    def boot(self) -> None:
        self.commands([PublishCommand])
