"""Tests for ServeCommand using Cleo's CommandTester.

Exercises option parsing, host/port resolution, and output messages without
starting a real Uvicorn server.  ``Config.get`` and ``uvicorn.run`` are patched
so the tests are self-contained with no live app or network required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

from cleo.testers.command_tester import CommandTester

from fastapi_startkit.fastapi.commands.serve_command import ServeCommand
from fastapi_startkit.fastapi.config import FastAPIConfig

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000
_DEFAULT_APP_URL = f"http://{_DEFAULT_HOST}:{_DEFAULT_PORT}"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def run(
    args: str = "",
    *,
    config: dict | None = None,
    app_found: bool = False,
) -> tuple[CommandTester, MagicMock]:
    """Execute ServeCommand with *args* and return (tester, mock_uvicorn).

    Parameters
    ----------
    args:
        Argument string forwarded verbatim to ``CommandTester.execute()``.
    config:
        Mapping of config keys to values that ``Config.get`` will return.
        Defaults to an empty dict (all keys fall back to their defaults).
    app_found:
        When ``True``, ``importlib.util.find_spec`` returns a non-None spec so
        that ``is_app_exist()`` yields ``True``.
    """
    cfg = config or {}

    def _config_get(key, default=None):
        return cfg.get(key, default)

    mock_uvicorn = MagicMock()
    mock_spec = MagicMock() if app_found else None

    with (
        patch("fastapi_startkit.fastapi.commands.serve_command.Config.get", side_effect=_config_get),
        patch("fastapi_startkit.configuration.config.Config.get", side_effect=_config_get),
        patch("uvicorn.run", mock_uvicorn),
        patch("importlib.util.find_spec", return_value=mock_spec),
    ):
        cmd = ServeCommand()
        tester = CommandTester(cmd)
        tester.execute(args, interactive=False)

    return tester, mock_uvicorn


# ---------------------------------------------------------------------------
# 1. Default behaviour — no CLI flags, no config, no app bootstrap module
# ---------------------------------------------------------------------------


class TestServeCommandDefaults:
    def test_exits_successfully(self):
        tester, _ = run()
        assert tester.status_code == 0

    def test_uvicorn_called(self):
        _, mock_uvicorn = run()
        mock_uvicorn.assert_called_once()

    def test_default_host_in_output(self):
        tester, _ = run()
        assert _DEFAULT_HOST in tester.io.fetch_output()

    def test_default_port_in_output(self):
        tester, _ = run()
        assert str(_DEFAULT_PORT) in tester.io.fetch_output()

    def test_uvicorn_kwargs_contain_ws(self):
        _, mock_uvicorn = run()
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("ws") == "websockets-sansio"


# ---------------------------------------------------------------------------
# 2. CLI --host / --port override defaults
# ---------------------------------------------------------------------------


class TestCliOptions:
    def test_custom_host_appears_in_output(self):
        tester, _ = run("--host 0.0.0.0")
        assert "0.0.0.0" in tester.io.fetch_output()

    def test_custom_port_appears_in_output(self):
        tester, _ = run("--port 9000")
        assert "9000" in tester.io.fetch_output()

    def test_host_and_port_together_in_output(self):
        tester, _ = run("--host 0.0.0.0 --port 9000")
        output = tester.io.fetch_output()
        assert "0.0.0.0" in output
        assert "9000" in output

    def test_custom_host_passed_to_uvicorn(self):
        _, mock_uvicorn = run("--host 0.0.0.0")
        _, kwargs = mock_uvicorn.call_args
        assert kwargs["host"] == "0.0.0.0"

    def test_custom_port_passed_to_uvicorn(self):
        _, mock_uvicorn = run("--port 9000")
        _, kwargs = mock_uvicorn.call_args
        assert kwargs["port"] == 9000


# ---------------------------------------------------------------------------
# 3. Config-driven host / port (no CLI flags)
# ---------------------------------------------------------------------------


class TestConfigOptions:
    def test_config_host_used_when_no_cli_flag(self):
        tester, _ = run(config={"fastapi.host": "10.0.0.1", "fastapi.app_url": "http://10.0.0.1:8000"})
        assert "10.0.0.1" in tester.io.fetch_output()

    def test_config_port_used_when_no_cli_flag(self):
        tester, _ = run(config={"fastapi.port": 7777, "fastapi.app_url": "http://127.0.0.1:7777"})
        assert "7777" in tester.io.fetch_output()

    def test_app_url_is_single_source_of_truth(self):
        """resolve_url() uses fastapi.app_url as the single source of truth.

        When fastapi.app_url is set in config and no CLI --host/--port flags are
        provided, the host and port are derived directly from the configured URL.
        """
        tester, _ = run(config={"fastapi.app_url": "http://staging.example.com:5000"})
        output = tester.io.fetch_output()
        # app_url is the source of truth — staging.example.com:5000 is used directly.
        assert "staging.example.com" in output
        assert "5000" in output


# ---------------------------------------------------------------------------
# 4. App bootstrap detected (is_app_exist → True)
# ---------------------------------------------------------------------------


class TestAppFound:
    def test_app_label_in_output(self):
        tester, _ = run("--app myapp.bootstrap:app", app_found=True)
        assert "myapp.bootstrap:app" in tester.io.fetch_output()

    def test_uvicorn_called_with_factory_true(self):
        _, mock_uvicorn = run(app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("factory") is True

    def test_uvicorn_called_with_app_string(self):
        _, mock_uvicorn = run("--app myapp.bootstrap:app", app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("app") == "myapp.bootstrap:app"


# ---------------------------------------------------------------------------
# 5. App bootstrap NOT found (is_app_exist → False)
# ---------------------------------------------------------------------------


class TestAppNotFound:
    def test_no_factory_kwarg_when_app_not_found(self):
        _, mock_uvicorn = run(app_found=False)
        _, kwargs = mock_uvicorn.call_args
        assert "factory" not in kwargs

    def test_reload_disabled_when_app_not_found(self):
        _, mock_uvicorn = run(app_found=False)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload") is False


# ---------------------------------------------------------------------------
# 6. FastAPIConfig is the single source of truth for defaults
# ---------------------------------------------------------------------------


class TestConfigBackedDefaults:
    """With no CLI flag and no registered config, values come from FastAPIConfig."""

    def test_default_app_url_matches_config_dataclass(self):
        tester, _ = run()
        assert urlsplit(FastAPIConfig().app_url).hostname in tester.io.fetch_output()

    def test_default_app_matches_config_dataclass(self):
        _, mock_uvicorn = run(app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("app") == FastAPIConfig().app

    def test_default_reload_matches_config_dataclass(self):
        _, mock_uvicorn = run(app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload") == FastAPIConfig().reload

    def test_default_reload_excludes_matches_config_dataclass(self):
        _, mock_uvicorn = run(app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload_excludes") == FastAPIConfig().reload_excludes


class TestConfigOverridesDefault:
    """A registered `fastapi` config wins over the FastAPIConfig default."""

    def test_config_app_used_when_no_cli_flag(self):
        _, mock_uvicorn = run(config={"fastapi.app": "custom.boot:app"}, app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("app") == "custom.boot:app"

    def test_config_reload_disables_reload(self):
        _, mock_uvicorn = run(config={"fastapi.reload": False}, app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload") is False

    def test_config_reload_dirs_passed_to_uvicorn(self):
        _, mock_uvicorn = run(config={"fastapi.reload_dirs": ["src"]}, app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload_dirs") == ["src"]

    def test_reload_dirs_omitted_when_reload_disabled(self):
        _, mock_uvicorn = run(
            config={"fastapi.reload_dirs": ["src"], "fastapi.reload": False},
            app_found=True,
        )
        _, kwargs = mock_uvicorn.call_args
        assert "reload_dirs" not in kwargs


class TestCliOverridesConfig:
    """An explicit CLI flag still wins over the config-provided default."""

    def test_cli_app_beats_config_app(self):
        _, mock_uvicorn = run(
            "--app cli.boot:app",
            config={"fastapi.app": "config.boot:app"},
            app_found=True,
        )
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("app") == "cli.boot:app"

    def test_cli_reload_beats_config_reload(self):
        _, mock_uvicorn = run("--reload true", config={"fastapi.reload": False}, app_found=True)
        _, kwargs = mock_uvicorn.call_args
        assert kwargs.get("reload") is True

    def test_cli_host_beats_config_app_url(self):
        tester, _ = run("--host 0.0.0.0", config={"fastapi.app_url": "http://10.0.0.1:8000"})
        assert "0.0.0.0" in tester.io.fetch_output()
