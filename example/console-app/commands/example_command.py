from cleo.commands.command import Command
from cleo.helpers import argument

from fastapi_startkit.logging import Logger


class ExampleCommand(Command):
    name = "hello"
    description = "This command greet the users."

    arguments = [
        argument("name", description="Who do you want to greet?", optional=True)
    ]

    def handle(self):
        name = self.argument("name")
        if name:
            text = "Hello {}".format(name)
        else:
            text = "Hello"

        # Example of showing loggings
        Logger.info(text)
        Logger.emergency("Hello, this is emergency")

        self.line(text)
