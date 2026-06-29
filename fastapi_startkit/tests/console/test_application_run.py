"""Tests for Application.run() — invoking a registered console command from Python.

A dummy command is registered on a fresh Application so the programmatic API can
resolve and execute it without touching ``sys.argv``.
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
    DummyCommand.exit_code = 0
    DummyCommand.received = {}

    previous = Container._instance
    application = Application(env="testing")
    application.add_commands([DummyCommand])
    yield application
    Container.set_instance(previous)


def test_run_returns_zero_exit_code(app):
    assert app.run("dummy:do") == 0


def test_run_propagates_non_zero_exit_code(app):
    DummyCommand.exit_code = 3

    assert app.run("dummy:do") == 3


def test_run_without_args(app):
    app.run("dummy:do")

    assert DummyCommand.received == {"name": None, "force": False}


def test_run_forwards_string_args(app):
    app.run("dummy:do", "hello --force")

    assert DummyCommand.received == {"name": "hello", "force": True}


def test_run_forwards_list_args(app):
    app.run("dummy:do", ["hello", "--force"])

    assert DummyCommand.received == {"name": "hello", "force": True}
