from typing import TYPE_CHECKING

from cleo.application import Application as BaseApplication
from cleo.io.io import IO

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class ConsoleApplication(BaseApplication):
    def __init__(self, app: "Application"):
        super().__init__()
        self.app = app

        # Register commands from Application
        for command in self.app.commands:
            if isinstance(command, type):
                instance = command()
            else:
                instance = command

            instance.set_container(self.app)
            self.add(instance)

    def render_error(self, error: Exception, io: IO) -> None:
        self.app.exception_manager.report(error)
        super().render_error(error, io)

    def handle(self) -> int:
        return self.run()
