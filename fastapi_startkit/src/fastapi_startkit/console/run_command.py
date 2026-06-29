import shlex

from cleo.helpers import argument

from fastapi_startkit.console.command import Command


class RunCommand(Command):
    name = "run"
    description = "Run another registered console command programmatically."

    arguments = [
        argument(
            "command_name",
            description="The name of the command to run (e.g. db:migrate).",
        ),
        argument(
            "args",
            description="Arguments to forward to the command. Prefix forwarded options with -- "
            "(e.g. run db:seed -- --force).",
            optional=True,
            multiple=True,
        ),
    ]

    def handle(self) -> int:
        command = self.argument("command_name")
        forwarded = self.argument("args") or []

        # Cleo's `call` re-tokenizes the args string and binds it against the
        # target command merged with the application definition, whose first
        # positional is the command name. The name must therefore lead the
        # string, otherwise the first forwarded argument is swallowed by it.
        # shlex.join keeps tokens containing spaces intact.
        return self.call(command, shlex.join([command, *forwarded]))
