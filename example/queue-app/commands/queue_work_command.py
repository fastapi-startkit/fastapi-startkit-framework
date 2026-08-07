from cleo.helpers import option
from fastapi_startkit.console.command import Command


class QueueWorkCommand(Command):
    """
    Start the Taskiq queue worker.

    queue:work
    """

    name = "queue:work"
    description = "Start the Taskiq queue worker."

    options = [
        option(
            "workers",
            "w",
            "Number of worker processes to spawn.",
            flag=False,
            default=1,
        )
    ]

    def handle(self):
        from taskiq.cli.worker.args import WorkerArgs
        from taskiq.cli.worker.run import run_worker

        workers = int(self.option("workers"))

        args = WorkerArgs(
            broker="worker:broker",
            modules=["tasks.example_task"],
            workers=workers,
        )

        self.line(f"Starting queue worker with {workers} process(es)...")
        run_worker(args)
