from importlib.resources import files
from importlib.util import find_spec
from string import Template
from typing import ClassVar

from cleo.helpers import option
from cleo.io.inputs.option import Option

from fastapi_startkit.console.install_command import InstallCommand, ProviderEntry
from fastapi_startkit.installer.plan import DRIVER_CLASSES, define_database, project_name_for

MIGRATIONS_PATH = "databases/migrations"


class DbInstallCommand(InstallCommand):
    name = "db:install"
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

    def handle(self) -> int:
        status = super().handle()
        if status == 0:
            self.next_steps()
        return status

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

    def next_steps(self) -> None:
        section = define_database(self.option("driver"), project_name_for(self.base_path))
        self.line("")
        self.line("Next steps:")
        if find_spec("sqlalchemy") is None:
            self.line(
                f'  Install the database extra: <info>uv add "fastapi-startkit[{",".join(section.extras)}]"</info>'
            )
        self.line("  Add to .env:")
        for key, value in section.environment.items():
            self.line(f"    {key}={value}")
        if not (self.base_path / MIGRATIONS_PATH).is_dir():
            self.line(f"  Create the migrations directory: <info>mkdir -p {MIGRATIONS_PATH}</info>")
        self.line("  Create a migration: <info>uv run python artisan db:make:migration create_users_table</info>")
        self.line("  Run migrations: <info>uv run python artisan db:migrate</info>")
