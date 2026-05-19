from cleo.helpers import argument, option
import os
import pathlib
from inflection import camelize, underscore
from fastapi_startkit.console import Command


class MakeObserverCommand(Command):
    name = "observer"
    description = "Creates a new observer file."

    arguments = [argument("name", description="The name of the observer")]

    options = [
        option(
            "model",
            "m",
            flag=False,
            default="None",
            description="The name of the model",
        ),
        option(
            "directory",
            "d",
            flag=False,
            default="app/observers",
            description="The location of the observers directory",
        ),
    ]

    def handle(self):
        name = self.argument("name")
        model = self.option("model")
        if model == "None":
            model = name

        observer_directory = self.option("directory")

        with open(os.path.join(pathlib.Path(__file__).parent.absolute(), "stubs/observer.stub")) as fp:
            output = fp.read()
            output = output.replace("__CLASS__", camelize(name))
            output = output.replace("__MODEL_VARIABLE__", underscore(model))
            output = output.replace("__MODEL__", camelize(model))

        file_name = f"{camelize(name)}Observer.py"

        full_directory_path = os.path.join(os.getcwd(), observer_directory)

        if os.path.exists(os.path.join(full_directory_path, file_name)):
            self.line(f'<error>Observer "{name}" Already Exists ({full_directory_path}/{file_name})</error>')
            return

        os.makedirs(os.path.join(full_directory_path), exist_ok=True)

        with open(os.path.join(os.getcwd(), observer_directory, file_name), "w+") as fp:
            fp.write(output)

        self.info(f"Observer created: {file_name}")
