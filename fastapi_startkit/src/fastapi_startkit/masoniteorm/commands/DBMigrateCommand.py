import os

from cleo.helpers import option

from fastapi_startkit.console import Command
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator


class DBMigrateCommand(Command):
    name = "db:migrate"
    description = "Run the pending database migrations."

    options = [
        option(
            "migration",
            "m",
            flag=False,
            default="all",
            description="Migration's name to be migrated",
        ),
        option(
            "connection",
            "c",
            flag=False,
            default="default",
            description="The connection you want to run migrations on",
        ),
        option(
            "force",
            "f",
            flag=True,
            description="Force migrations without prompt in production",
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
        self.confirm_to_proceed()

        directory = self.resolve_migration_path()

        migration = Migrator(
            command_class=self,
            connection=self.option("connection"),
            migration_directory=directory,
        )

        await migration.create_table_if_not_exists()
        if not await migration.get_unran_migrations():
            self.info("Nothing To Migrate!")
            return

        migration_name = self.option("migration")

        await migration.migrate(migration=migration_name)

    def resolve_migration_path(self) -> str:
        path = self.option("directory")

        config = self.container.make("config").get("database.migrations")
        default_directory = config.get("directory")

        migration_directory = path or default_directory
        return self.container.use_base_path(migration_directory)

    def confirm_to_proceed(self) -> None:
        # prompt user for confirmation in production
        if os.getenv("APP_ENV") == "production" and not self.option("force"):
            answer = ""
            while answer not in ["y", "n"]:
                answer = input("Do you want to run migrations in PRODUCTION ? (y/n)\n").lower()
            if answer != "y":
                self.info("Migrations cancelled")
                exit(0)
