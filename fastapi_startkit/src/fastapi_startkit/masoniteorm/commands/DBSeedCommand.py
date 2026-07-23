from cleo.helpers import argument, option
from inflection import camelize, underscore

from fastapi_startkit.console import Command


class DBSeedCommand(Command):
    name = "db:seed"
    description = "Run seeds."

    arguments = [
        argument(
            "table",
            default="None",
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

    def handle(self):
        import asyncio

        return asyncio.run(self.handle_async())

    async def handle_async(self):
        from ..seeders import Seeder

        seeder = Seeder(
            seed_path=self.option("directory"),
            connection=self.option("connection"),
        )

        class_name = self.option("class")
        table = self.argument("table")

        if class_name:
            if "." in class_name:
                seeder_file = class_name
            else:
                # If only class name is provided, assume it's in a file named underscore(class_name)
                # e.g. PostSeeder -> post_seeder.PostSeeder
                # or if it ends with TableSeeder, handle that (backward compatibility with existing 'table' arg logic)
                if class_name.endswith("TableSeeder"):
                    base = class_name[:-11]  # Remove TableSeeder
                    seeder_file = f"{underscore(base)}_table_seeder.{class_name}"
                else:
                    seeder_file = f"{underscore(class_name)}.{camelize(class_name)}"

            await seeder.run_specific_seed(seeder_file)
            seeder_seeded = seeder_file.split(".")[-1]

        elif table != "None":
            seeder_file = f"{underscore(table)}_table_seeder.{camelize(table)}TableSeeder"
            await seeder.run_specific_seed(seeder_file)
            seeder_seeded = f"{camelize(table)}TableSeeder"

        else:
            await seeder.run_database_seed()
            seeder_seeded = "Database Seeder"

        self.line(f"<info>{seeder_seeded} seeded!</info>")
