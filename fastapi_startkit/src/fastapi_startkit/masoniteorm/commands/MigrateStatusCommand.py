from cleo.helpers import option
from fastapi_startkit.console import Command
from fastapi_startkit.masoniteorm.migrations.Migrator import Migrator


class MigrateStatusCommand(Command):
    name = "db:migrate:status"
    description = "Display migrations status."

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

        await migration.create_table_if_not_exists()
        table = self.table()
        table.set_headers(["Ran?", "Migration", "Batch"])
        migrations = []

        ran_migrations = await migration.get_ran_migrations()
        for migration_data in ran_migrations:
            migration_file = migration_data["migration_file"]
            batch = migration_data["batch"]

            migrations.append(
                [
                    "<info>Y</info>",
                    f"<comment>{migration_file}</comment>",
                    f"<info>{batch}</info>",
                ]
            )

        unran_migrations = await migration.get_unran_migrations()
        for migration_file in unran_migrations:
            migrations.append(
                [
                    "<error>N</error>",
                    f"<comment>{migration_file}</comment>",
                    "<info>-</info>",
                ]
            )

        table.set_rows(migrations)

        table.render()

    def resolve_migration_path(self) -> str:
        path = self.option("directory")

        config = self.container.make("config").get("database.migrations")
        default_directory = config.get("directory")

        migration_directory = path or default_directory
        return self.container.use_base_path(migration_directory)
