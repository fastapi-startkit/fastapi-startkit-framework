"""Unit tests for ``Application.run()``.

``Application.run()`` invokes an already-registered console command by name from
Python code — without going through ``sys.argv`` — and returns the command's
exit code. A dummy command is registered on a fresh ``Application`` so the
programmatic API has something concrete to resolve and execute.
"""

from __future__ import annotations

import unittest

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


class ApplicationRunTest(unittest.TestCase):
    def setUp(self) -> None:
        DummyCommand.exit_code = 0
        DummyCommand.received = {}

        # The container is a process-wide singleton; remember the current one
        # so it can be restored in tearDown and keep tests isolated.
        self._previous = Container._instance
        self.app = Application(env="testing")
        self.app.add_commands([DummyCommand])

    def tearDown(self) -> None:
        Container.set_instance(self._previous)

    # -- exit code ---------------------------------------------------------

    def test_returns_zero_exit_code_as_int(self):
        result = self.app.run("dummy:do")

        self.assertEqual(result, 0)
        self.assertIsInstance(result, int)

    def test_propagates_non_zero_exit_code(self):
        DummyCommand.exit_code = 3

        self.assertEqual(self.app.run("dummy:do"), 3)

    def test_unknown_command_returns_error_code(self):
        # Cleo reports the error through the application instead of raising; the
        # call still returns a non-zero exit code rather than terminating the host.
        self.assertEqual(self.app.run("does:not-exist"), 1)

    # -- argument handling -------------------------------------------------

    def test_runs_without_args(self):
        self.app.run("dummy:do")

        self.assertEqual(DummyCommand.received, {"name": None, "force": False})

    def test_none_args_is_equivalent_to_no_args(self):
        self.app.run("dummy:do", None)

        self.assertEqual(DummyCommand.received, {"name": None, "force": False})

    def test_empty_string_args_is_equivalent_to_no_args(self):
        self.app.run("dummy:do", "")

        self.assertEqual(DummyCommand.received, {"name": None, "force": False})

    def test_forwards_string_and_sequence_args(self):
        for args in ("hello --force", "hello -f", ["hello", "--force"], ("hello", "-f")):
            with self.subTest(args=args):
                DummyCommand.received = {}

                self.app.run("dummy:do", args)

                self.assertEqual(DummyCommand.received, {"name": "hello", "force": True})

    def test_forwards_positional_arg_only(self):
        self.app.run("dummy:do", "hello")

        self.assertEqual(DummyCommand.received, {"name": "hello", "force": False})

    def test_list_arg_preserves_value_with_spaces(self):
        self.app.run("dummy:do", ["hello world"])

        self.assertEqual(DummyCommand.received["name"], "hello world")

    def test_non_string_list_args_are_stringified(self):
        self.app.run("dummy:do", [123])

        self.assertEqual(DummyCommand.received["name"], "123")

    # -- re-entrancy -------------------------------------------------------

    def test_can_be_invoked_repeatedly(self):
        self.assertEqual(self.app.run("dummy:do", "first"), 0)
        self.assertEqual(DummyCommand.received["name"], "first")

        self.assertEqual(self.app.run("dummy:do", "second --force"), 0)
        self.assertEqual(DummyCommand.received, {"name": "second", "force": True})


if __name__ == "__main__":
    unittest.main()
