from fastapi_startkit.providers import Provider
from commands.queue_work_command import QueueWorkCommand


class ConsoleProvider(Provider):
    def register(self) -> None:
        pass

    def boot(self) -> None:
        self.app.add_commands(
            [
                QueueWorkCommand,
            ]
        )
