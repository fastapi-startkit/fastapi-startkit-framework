"""Tests for ServeCommand --reload bool coercion (using Cleo CommandTester)."""

from unittest.mock import patch

from cleo.testers.command_tester import CommandTester

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


def _run(args: str, cfg_reload: bool = True) -> dict:
    """
    Execute ServeCommand via CommandTester and return the kwargs dict that
    was passed to uvicorn.run().

    CommandTester drives the full handle() path — option() is resolved by
    Cleo from the parsed *args* string, so we never patch option() here.
    External I/O (uvicorn, Config, is_app_exist) is patched so the server
    never actually starts.
    """
    cfg = {**_CONFIG_DEFAULTS, "fastapi.reload": cfg_reload}

    cmd = ServeCommand()
    tester = CommandTester(cmd)

    with (
        patch.object(Config, "get", side_effect=lambda key, default=None: cfg.get(key, default)),
        patch("uvicorn.run") as mock_uvicorn,
        patch.object(ServeCommand, "is_app_exist", return_value=True),
    ):
        tester.execute(args)
        return mock_uvicorn.call_args[1]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestServeCommandReloadCoercion:
    def test_reload_string_false_becomes_bool_false(self):
        """--reload False (string) must be coerced to bool False."""
        kwargs = _run("--reload False")
        assert kwargs["reload"] is False

    def test_reload_string_true_becomes_bool_true(self):
        """--reload True (string) must be coerced to bool True."""
        kwargs = _run("--reload True")
        assert kwargs["reload"] is True

    def test_no_reload_flag_uses_cfg_default_true(self):
        """No --reload flag: reload should inherit the fastapi config value (True)."""
        kwargs = _run("", cfg_reload=True)
        assert kwargs["reload"] is True

    def test_no_reload_flag_uses_cfg_default_false(self):
        """No --reload flag with cfg=False: reload should be False."""
        kwargs = _run("", cfg_reload=False)
        assert kwargs["reload"] is False

    def test_reload_string_false_lowercase_becomes_bool_false(self):
        """--reload false (lowercase) must also be coerced to bool False."""
        kwargs = _run("--reload false")
        assert kwargs["reload"] is False
