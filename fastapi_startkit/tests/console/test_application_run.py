"""Unit tests for ``Application.run()``.

``Application.run()`` invokes an already-registered console command by name from
Python code — without going through ``sys.argv`` — and returns the command's
exit code. A dummy command is registered on a fresh ``Application`` so the
programmatic API has something concrete to resolve and execute.
"""

from __future__ import annotations

import pytest
from cleo.helpers import argument, option

from fastapi_startkit.application import Application
from fastapi_startkit.console import Command
from fastapi_startkit.container import Container


class DummyCommand(Command):
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


@pytest.fixture
def app():
    """A booted Application with DummyCommand registered.

    The container is a process-wide singleton, so the previous instance is
    restored on teardown to keep these tests isolated from the rest of the
    suite.
    """
    DummyCommand.exit_code = 0
    DummyCommand.received = {}

    previous = Container._instance
    application = Application(env="testing")
    application.add_commands([DummyCommand])
    yield application
    Container.set_instance(previous)


# ---------------------------------------------------------------------------
# Exit code
# ---------------------------------------------------------------------------


def test_returns_zero_exit_code_as_int(app):
    result = app.run("dummy:do")

    assert result == 0
    assert isinstance(result, int)


def test_propagates_non_zero_exit_code(app):
    DummyCommand.exit_code = 3

    assert app.run("dummy:do") == 3


def test_unknown_command_returns_error_code(app):
    # Cleo reports the error through the application instead of raising; the
    # call still returns a non-zero exit code rather than terminating the host.
    assert app.run("does:not-exist") == 1


# ---------------------------------------------------------------------------
# Argument handling
# ---------------------------------------------------------------------------


def test_runs_without_args(app):
    app.run("dummy:do")

    assert DummyCommand.received == {"name": None, "force": False}


def test_none_args_is_equivalent_to_no_args(app):
    app.run("dummy:do", None)

    assert DummyCommand.received == {"name": None, "force": False}


def test_empty_string_args_is_equivalent_to_no_args(app):
    app.run("dummy:do", "")

    assert DummyCommand.received == {"name": None, "force": False}


@pytest.mark.parametrize(
    "args",
    [
        "hello --force",
        "hello -f",
        ["hello", "--force"],
        ("hello", "-f"),
    ],
)
def test_forwards_string_and_sequence_args(app, args):
    app.run("dummy:do", args)

    assert DummyCommand.received == {"name": "hello", "force": True}


def test_forwards_positional_arg_only(app):
    app.run("dummy:do", "hello")

    assert DummyCommand.received == {"name": "hello", "force": False}


def test_list_arg_preserves_value_with_spaces(app):
    app.run("dummy:do", ["hello world"])

    assert DummyCommand.received["name"] == "hello world"


def test_non_string_list_args_are_stringified(app):
    app.run("dummy:do", [123])

    assert DummyCommand.received["name"] == "123"


# ---------------------------------------------------------------------------
# Re-entrancy
# ---------------------------------------------------------------------------


def test_can_be_invoked_repeatedly(app):
    assert app.run("dummy:do", "first") == 0
    assert DummyCommand.received["name"] == "first"

    assert app.run("dummy:do", "second --force") == 0
    assert DummyCommand.received == {"name": "second", "force": True}
