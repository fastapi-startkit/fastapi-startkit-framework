from fastapi_startkit.console.publish_command import PublishCommand
from fastapi_startkit.console.run_command import RunCommand
from fastapi_startkit.providers import Provider


class AppProvider(Provider):
    def register(self) -> None:
        pass

    def boot(self) -> None:
        self.commands([PublishCommand, RunCommand])
