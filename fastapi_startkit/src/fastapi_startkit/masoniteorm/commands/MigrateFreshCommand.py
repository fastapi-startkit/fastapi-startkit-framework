from cleo.helpers import option
from fastapi_startkit.console import Command
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator


class MigrateFreshCommand(Command):
    name = "db:migrate:fresh"
    description = "Fresh migrations."

    options = [
        option(
            "connection",
            "c",
            flag=False,
            default="default",
            description="The connection you want to run migrations on",
        ),
        option(
            "directory",
            "d",
            flag=False,
            default="databases/migrations",
            description="The location of the migration directory",
        ),
        option(
            "no-fk",
            None,
            flag=True,
            description="Re-enable foreign key constraints during drop",
        ),
        option(
            "seed",
            "s",
            flag=False,
            default=None,
            description="Seed the database after fresh",
        ),
        option(
            "seed-directory",
            None,
            flag=False,
            default="databases/seeds",
            description="The location of the seed directory",
        ),
    ]

    def handle(self):
        import asyncio

        return asyncio.run(self.handle_async())

    async def handle_async(self):
        directory = self.resolve_migration_path()

        migration = Migrator(
            command_class=self,
            connection=self.option("connection"),
            migration_directory=directory,
        )

        await migration.fresh(ignore_fk=not self.option("no-fk"))

        if self.option("seed") == "null":
            self.call(
                "seed:run",
                f"None --directory {self.option('seed-directory')} --connection {self.option('connection')}",
            )
        elif self.option("seed"):
            self.call(
                "seed:run",
                f"{self.option('seed')} --directory {self.option('seed-directory')} --connection {self.option('connection')}",
            )

    def resolve_migration_path(self) -> str:
        path = self.option("directory")

        config = self.container.make("config").get("database.migrations")
        default_directory = config.get("directory")

        migration_directory = path or default_directory
        return self.container.use_base_path(migration_directory)
