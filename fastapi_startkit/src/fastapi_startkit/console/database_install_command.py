from importlib.resources import files
from string import Template
from typing import ClassVar

from cleo.helpers import option
from cleo.io.inputs.option import Option

from fastapi_startkit.console.install_command import InstallCommand, ProviderEntry
from fastapi_startkit.installer.plan import DRIVER_CLASSES


class DatabaseInstallCommand(InstallCommand):
    name = "database:install"
    description = "Publish config/database.py and register DatabaseProvider in bootstrap/application.py."

    providers = (ProviderEntry.of("fastapi_startkit.masoniteorm.DatabaseProvider", "config.database.DatabaseConfig"),)

    options: ClassVar[list[Option]] = [
        *InstallCommand.options,
        option(
            "driver",
            "d",
            description=f"Database driver: {', '.join(DRIVER_CLASSES)}.",
            flag=False,
            default="sqlite",
        ),
    ]

    def publish(self) -> int:
        driver = self.option("driver")
        if driver not in DRIVER_CLASSES:
            self.line_error(f"<error>Unsupported driver '{driver}'. Use one of: {', '.join(DRIVER_CLASSES)}.</error>")
            return 1

        stub = files("fastapi_startkit.installer").joinpath("stubs/database/config.py.stub").read_text(encoding="utf-8")
        self.publish_file(
            "config/database.py",
            Template(stub).substitute(driver=driver, driver_class=DRIVER_CLASSES[driver]),
        )
        return 0
