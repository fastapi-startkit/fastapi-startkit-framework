import subprocess
import sys

from cleo.helpers import option
from fastapi_startkit.console.command import Command


class QueueWorkCommand(Command):
    name = "queue:work"
    description = "Start the TaskIQ worker."
    options = [option("workers", "w", "Number of worker processes", flag=False, default="1")]

    def handle(self):
        try:
            workers = int(self.option("workers"))
            if workers < 1:
                raise ValueError
        except (TypeError, ValueError):
            self.line_error("--workers must be a positive integer", style="error")
            return 1
        return subprocess.run([
            sys.executable, "-m", "taskiq", "worker", "worker:broker", "tasks.example_task", "--workers", str(workers),
        ], check=False).returncode
