import os
import shutil
from typing import TYPE_CHECKING

from fastapi_startkit.console import Command
from cleo.helpers import option
from fastapi_startkit.support import Str

if TYPE_CHECKING:
    from fastapi_startkit.application import Application


class PublishCommand(Command):
    name = "provider:publish"
    description = "Publish provider config files into the project."

    options = [
        option(
            "provider",
            "p",
            description="Provider name to publish (e.g. LogProvider, log_provider).",
            flag=False,
        ),
    ]

    def handle(self):
        from fastapi_startkit.application import app

        application: "Application" = app()

        if not application.published_resources:
            self.line("<comment>Nothing to publish.</comment>")
            return

        provider_arg = self.option("provider")

        if provider_arg:
            target = Str.slugify(provider_arg)
            resources = {
                name: files for name, files in application.published_resources.items() if Str.slugify(name) == target
            }
            if not resources:
                self.line(f"<error>No provider found matching '{provider_arg}'.</error>")
                return
        else:
            resources = application.published_resources

        for provider_key, files in resources.items():
            for source, destination in files.items():
                dest_path = application.use_base_path(destination)

                if os.path.exists(dest_path):
                    overwrite = self.confirm(
                        f"  <comment>{destination}</comment> already exists. Overwrite?",
                        default=False,
                    )
                    if not overwrite:
                        self.line(f"  [{provider_key}] Skipped <comment>{destination}</comment>")
                        continue

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy2(source, dest_path)
                self.line(f"  [{provider_key}] Published <info>{destination}</info>")
