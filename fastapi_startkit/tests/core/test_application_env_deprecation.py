import sys
import warnings

import pytest

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container


@pytest.fixture(autouse=True)
def restore_container_instance():
    original = Container._instance
    yield
    Container._instance = original


def test_passing_env_warns_at_the_call_site(tmp_path):
    with pytest.warns(DeprecationWarning, match=r"removed in 1\.0.*APP_ENV.*--env") as record:
        Application(base_path=tmp_path, env="testing")

    assert record[0].filename == __file__


def test_passing_env_still_selects_the_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST")

    with pytest.warns(DeprecationWarning):
        app = Application(base_path=tmp_path, env="staging")

    assert app.env == "staging"


def test_no_warning_without_env(tmp_path):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        app = Application(base_path=tmp_path)

    assert app.env == "testing"


def test_app_env_variable_selects_the_environment_without_warning(tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.setenv("APP_ENV", "production")

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        app = Application(base_path=tmp_path)

    assert app.env == "production"


@pytest.mark.parametrize("argv", [["--env", "production"], ["--env=production"]])
def test_cli_env_option_selects_the_environment_without_warning(tmp_path, monkeypatch, argv):
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.setenv("APP_ENV", "")
    monkeypatch.setattr(sys, "argv", ["artisan", "serve", *argv])

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        app = Application(base_path=tmp_path)

    assert app.env == "production"
    assert sys.argv == ["artisan", "serve"]
