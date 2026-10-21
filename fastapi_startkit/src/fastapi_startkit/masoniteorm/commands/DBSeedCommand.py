from cleo.helpers import argument, option
from inflection import camelize, underscore

from fastapi_startkit.console import Command


class DBSeedCommand(Command):
    name = "db:seed"
    description = "Run seeds."

    arguments = [
        argument(
            "table",
            default=None,
            description="Name of the table to seed",
            optional=True,
        )
    ]

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
            default="databases/seeders",
            description="The location of the seed directory",
        ),
        option(
            "class",
            None,
            flag=False,
            description="Specific seeder class to run",
        ),
    ]

    def handle(self) -> int:
        import asyncio

        asyncio.run(self.handle_async())
        return 0

    async def handle_async(self):
        seeded = await self.run_seeders(
            directory=self.option("directory"),
            connection=self.option("connection"),
            table=self.argument("table"),
            class_name=self.option("class"),
        )
        self.line(f"<info>{seeded} seeded!</info>")

    @staticmethod
    async def run_seeders(directory: str, connection: str, table: str | None = None, class_name: str | None = None) -> str:
        from ..seeders import Seeder

        seeder = Seeder(seed_path=directory, connection=connection)

        if class_name:
            if "." in class_name:
                seeder_file = class_name
            elif class_name.endswith("TableSeeder"):
                seeder_file = f"{underscore(class_name[:-11])}_table_seeder.{class_name}"
            else:
                seeder_file = f"{underscore(class_name)}.{camelize(class_name)}"

            await seeder.run_specific_seed(seeder_file)
            return seeder_file.split(".")[-1]

        if table:
            await seeder.run_specific_seed(f"{underscore(table)}_table_seeder.{camelize(table)}TableSeeder")
            return f"{camelize(table)}TableSeeder"

        await seeder.run_database_seed()
        return "Database Seeder"
