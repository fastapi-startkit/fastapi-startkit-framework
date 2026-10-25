import os
import pathlib
from inflection import camelize, tableize, underscore
from fastapi_startkit.console import Command
from cleo.helpers import argument, option


class MakeModelCommand(Command):
    name = "db:make:model"
    description = "Creates a new model file."

    arguments = [argument("name", description="The name of the model")]

    options = [
        option(
            "migration",
            "m",
            description="Optionally create a migration file",
            flag=True,
        ),
        option("seeder", "s", description="Optionally create a seeder file", flag=True),
        option(
            "create",
            "c",
            description="If the migration file should create a table",
            flag=True,
        ),
        option(
            "table",
            "t",
            description="If the migration file should modify an existing table",
            flag=True,
        ),
        option("pep", "p", description="Makes the file into pep 8 standards", flag=True),
        option(
            "directory",
            "d",
            flag=False,
            default="app",
            description="The location of the model directory",
        ),
        option(
            "migrations-directory",
            "D",
            flag=False,
            default="databases/migrations",
            description="The location of the migration directory",
        ),
        option(
            "seeders-directory",
            "S",
            flag=False,
            default="databases/seeders",
            description="The location of the seeders directory",
        ),
    ]

    def handle(self) -> int:
        name = self.argument("name")

        model_directory = self.option("directory")

        with open(os.path.join(pathlib.Path(__file__).parent.absolute(), "stubs/model.stub")) as fp:
            output = fp.read()
            output = output.replace("__CLASS__", camelize(name))

        if self.option("pep"):
            file_name = f"{underscore(name)}.py"
        else:
            file_name = f"{camelize(name)}.py"

        full_directory_path = os.path.join(os.getcwd(), model_directory)

        if os.path.exists(os.path.join(full_directory_path, file_name)):
            self.line(f'<error>Model "{name}" Already Exists ({full_directory_path}/{file_name})</error>')
            return 0

        os.makedirs(os.path.dirname(os.path.join(full_directory_path)), exist_ok=True)

        with open(os.path.join(os.getcwd(), model_directory, file_name), "w+") as fp:
            fp.write(output)

        self.info(f"Model created: {os.path.join(model_directory, file_name)}")
        if self.option("migration"):
            table = tableize(name)
            if self.option("table"):
                arguments = f"update_{table}_table --table {table}"
            else:
                arguments = f"create_{table}_table --create {table}"
            self.call_command("db:make:migration", f"{arguments} --directory {self.option('migrations-directory')}")

        if self.option("seeder"):
            self.call_command("seed", f"{name} --directory {self.option('seeders-directory')}")

        return 0

    def call_command(self, name: str, arguments: str) -> int:
        return self.call(name, f"{name} {arguments}")
