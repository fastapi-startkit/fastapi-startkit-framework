"""Tests for RunCommand.

RunCommand is a thin wrapper that invokes another registered command via
Cleo's ``Command.call`` and propagates its exit code.  A dummy command is
registered alongside RunCommand on a real Cleo application so that
``self.call`` can resolve it.
"""

from __future__ import annotations

from cleo.application import Application
from cleo.commands.command import Command as CleoCommand
from cleo.helpers import argument, option
from cleo.testers.command_tester import CommandTester

from fastapi_startkit.console.run_command import RunCommand


class _DummyCommand(CleoCommand):
    name = "dummy:do"
    description = "Records what it received and returns a configurable exit code."

    arguments = [argument("name", optional=True)]
    options = [option("force", "f", description="Force flag.", flag=True)]

    exit_code = 0
    received: dict = {}

    def handle(self) -> int:
        type(self).received = {
            "name": self.argument("name"),
            "force": self.option("force"),
        }
        return type(self).exit_code


def _tester(exit_code: int = 0) -> CommandTester:
    _DummyCommand.exit_code = exit_code
    _DummyCommand.received = {}

    app = Application()
    app.add(_DummyCommand())
    app.add(RunCommand())

    return CommandTester(app.find("run"))


def test_forwards_positional_argument() -> None:
    tester = _tester()

    status = tester.execute("dummy:do hello")

    assert status == 0
    assert _DummyCommand.received["name"] == "hello"


def test_propagates_non_zero_exit_code() -> None:
    tester = _tester(exit_code=5)

    status = tester.execute("dummy:do hello")

    assert status == 5


def test_forwards_options_after_separator() -> None:
    tester = _tester()

    status = tester.execute("dummy:do hello -- --force")

    assert status == 0
    assert _DummyCommand.received["force"] is True


def test_runs_command_without_extra_args() -> None:
    tester = _tester()

    status = tester.execute("dummy:do")

    assert status == 0
    assert _DummyCommand.received["name"] is None
