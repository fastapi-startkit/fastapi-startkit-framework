from pathlib import Path
from typing import override

from cleo.helpers import argument, option
from inflection import camelize, underscore

from fastapi_startkit.console import Command

STUB = Path(__file__).resolve().parent / "stubs" / "notification.stub"


class MakeNotificationCommand(Command):
    name = "make:notification"
    description = "Creates a new notification class."

    arguments = [argument("name", description="The name of the notification")]

    options = [
        option(
            "directory",
            "d",
            flag=False,
            default="app/notifications",
            description="The location of the notifications directory",
        ),
    ]

    @override
    def handle(self) -> int:
        class_name = camelize(self.argument("name"))
        directory = Path.cwd() / self.option("directory")
        target = directory / f"{underscore(class_name)}.py"

        if target.exists():
            self.line(f'<error>Notification "{class_name}" already exists ({target})</error>')
            return 1

        directory.mkdir(parents=True, exist_ok=True)
        target.write_text(STUB.read_text().replace("__CLASS__", class_name))
        self.info(f"Notification created: {target}")
        return 0
