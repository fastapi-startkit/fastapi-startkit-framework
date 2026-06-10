"""Tests for ServeCommand --reload bool coercion."""

from unittest.mock import patch

from fastapi_startkit.configuration.config import Config
from fastapi_startkit.fastapi.commands.serve_command import ServeCommand


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    "fastapi.host": "127.0.0.1",
    "fastapi.port": 8000,
    "fastapi.reload": True,
    "fastapi.reload_dirs": None,
    "fastapi.reload_excludes": None,
}


def _make_options(reload_value, host=None, port=None, app="bootstrap.application:app"):
    """Return a side_effect function for ServeCommand.option()."""
    mapping = {
        "reload": reload_value,
        "host": host,
        "port": port,
        "app": app,
    }
    return lambda key: mapping[key]


def _run_handle(reload_option_value, cfg_reload=True):
    """
    Instantiate ServeCommand, mock its dependencies, call handle(), and return
    the kwargs dict that was passed to uvicorn.run.

    Config and uvicorn are both imported inside handle(), so we patch them at
    their canonical module paths rather than on the serve_command module.
    """
    cmd = ServeCommand.__new__(ServeCommand)

    config_map = {**_CONFIG_DEFAULTS, "fastapi.reload": cfg_reload}

    with (
        patch.object(Config, "get", side_effect=lambda key, default=None: config_map.get(key, default)),
        patch("uvicorn.run") as mock_uvicorn_run,
        patch.object(ServeCommand, "is_app_exist", return_value=True),
        patch.object(ServeCommand, "line"),
        patch.object(ServeCommand, "option", side_effect=_make_options(reload_option_value)),
    ):
        cmd.handle()
        return mock_uvicorn_run.call_args[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestServeCommandReloadCoercion:
    def test_reload_none_falls_back_to_cfg_reload_true(self):
        """When --reload is not passed, reload inherits the fastapi config value."""
        kwargs = _run_handle(reload_option_value=None, cfg_reload=True)
        assert kwargs["reload"] is True

    def test_reload_none_falls_back_to_cfg_reload_false(self):
        """When --reload is not passed and cfg is False, reload is False."""
        kwargs = _run_handle(reload_option_value=None, cfg_reload=False)
        assert kwargs["reload"] is False

    def test_reload_string_False_becomes_bool_false(self):
        """--reload=False (string) must be coerced to bool False."""
        kwargs = _run_handle(reload_option_value="False")
        assert kwargs["reload"] is False

    def test_reload_string_True_becomes_bool_true(self):
        """--reload=True (string) must be coerced to bool True."""
        kwargs = _run_handle(reload_option_value="True")
        assert kwargs["reload"] is True

    def test_reload_string_false_lowercase_becomes_bool_false(self):
        """--reload=false (lowercase) must be coerced to bool False."""
        kwargs = _run_handle(reload_option_value="false")
        assert kwargs["reload"] is False
