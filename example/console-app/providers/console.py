from commands.example_command import ExampleCommand
from fastapi_startkit.providers import Provider


class ConsoleServiceProvider(Provider):
    def register(self):
        pass

    def boot(self):
        self.app.add_commands([ExampleCommand])
