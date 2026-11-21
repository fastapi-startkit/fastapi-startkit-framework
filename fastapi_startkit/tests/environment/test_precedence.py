import os
import sys
from pathlib import Path

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.environment import env, value


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    original = Container._instance
    for key in ("APP_ENV", "PRECEDENCE_DB_HOST", "PRECEDENCE_MARKER", "PRECEDENCE_ONLY_BASE", "PRECEDENCE_RELOADED"):
        monkeypatch.delenv(key, raising=False)
    yield
    Container._instance = original


def leave_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST")


def write(base: Path, name: str, content: str) -> None:
    (base / name).write_text(content)


def assert_environment_agrees(app: Application, expected: str) -> None:
    assert app.env == expected
    assert os.environ["APP_ENV"] == expected
    assert value(env("APP_ENV")) == expected
    assert app.config.env == expected


def test_shell_app_env_beats_app_env_in_dotenv(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "APP_ENV=local\n")
    write(tmp_path, ".env.production", "PRECEDENCE_MARKER=production-file\n")
    monkeypatch.setenv("APP_ENV", "production")

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "production")
    assert os.environ["PRECEDENCE_MARKER"] == "production-file"


@pytest.mark.parametrize("argv", [["--env", "production"], ["--env=production"]])
def test_env_option_beats_app_env_in_dotenv(tmp_path, monkeypatch, argv):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "APP_ENV=local\n")
    write(tmp_path, ".env.production", "PRECEDENCE_MARKER=production-file\n")
    monkeypatch.setattr(sys, "argv", ["artisan", "serve", *argv])

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "production")
    assert os.environ["PRECEDENCE_MARKER"] == "production-file"


def test_env_option_beats_shell_app_env_and_dotenv(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "APP_ENV=local\n")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setattr(sys, "argv", ["artisan", "--env=production"])

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "production")


def test_dotenv_app_env_is_used_when_nothing_else_selects_the_environment(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "APP_ENV=local\n")

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "local")


def test_env_specific_file_cannot_change_app_env(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env.production", "APP_ENV=staging\n")
    monkeypatch.setenv("APP_ENV", "production")

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "production")


def test_shell_variable_beats_dotenv_and_env_specific_file(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "PRECEDENCE_DB_HOST=from-base\n")
    write(tmp_path, ".env.production", "PRECEDENCE_DB_HOST=from-production\n")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRECEDENCE_DB_HOST", "from-shell")

    Application(base_path=tmp_path)

    assert os.environ["PRECEDENCE_DB_HOST"] == "from-shell"


def test_env_specific_file_beats_dotenv_for_unset_variables(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "PRECEDENCE_DB_HOST=from-base\nPRECEDENCE_ONLY_BASE=base-only\n")
    write(tmp_path, ".env.production", "PRECEDENCE_DB_HOST=from-production\n")
    monkeypatch.setenv("APP_ENV", "production")

    Application(base_path=tmp_path)

    assert os.environ["PRECEDENCE_DB_HOST"] == "from-production"
    assert os.environ["PRECEDENCE_ONLY_BASE"] == "base-only"


def test_pytest_detection_loads_env_testing_over_dotenv(tmp_path):
    write(tmp_path, ".env", "APP_ENV=local\nPRECEDENCE_DB_HOST=from-base\n")
    write(tmp_path, ".env.testing", "PRECEDENCE_DB_HOST=from-testing\n")

    app = Application(base_path=tmp_path)

    assert_environment_agrees(app, "testing")
    assert os.environ["PRECEDENCE_DB_HOST"] == "from-testing"


def test_reload_keeps_shell_variables_and_refreshes_file_values(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env", "PRECEDENCE_DB_HOST=from-base\nPRECEDENCE_RELOADED=first\n")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("PRECEDENCE_DB_HOST", "from-shell")
    app = Application(base_path=tmp_path)
    assert os.environ["PRECEDENCE_RELOADED"] == "first"

    write(tmp_path, ".env", "PRECEDENCE_DB_HOST=from-base\nPRECEDENCE_RELOADED=second\n")
    app.load_environment()

    assert os.environ["PRECEDENCE_DB_HOST"] == "from-shell"
    assert os.environ["PRECEDENCE_RELOADED"] == "second"


def test_set_environment_reload_switches_app_env_everywhere(tmp_path, monkeypatch):
    leave_pytest(monkeypatch)
    write(tmp_path, ".env.production", "PRECEDENCE_MARKER=production-file\n")
    monkeypatch.setenv("APP_ENV", "staging")
    app = Application(base_path=tmp_path)

    app.set_environment("production").load_environment()

    assert os.environ["APP_ENV"] == "production"
    assert os.environ["PRECEDENCE_MARKER"] == "production-file"
