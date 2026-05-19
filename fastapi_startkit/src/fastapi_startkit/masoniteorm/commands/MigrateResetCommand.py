from cleo.helpers import option
from fastapi_startkit.console import Command
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator


class MigrateResetCommand(Command):
    name = "db:migrate:reset"
    description = "Reset migrations."

    options = [
        option(
            "migration",
            "m",
            flag=False,
            default="all",
            description="Migration's name to be rollback",
        ),
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

        await migration.reset(self.option("migration"))

    def resolve_migration_path(self) -> str:
        path = self.option("directory")

        config = self.container.make("config").get("database.migrations")
        default_directory = config.get("directory")

        migration_directory = path or default_directory
        return self.container.use_base_path(migration_directory)
