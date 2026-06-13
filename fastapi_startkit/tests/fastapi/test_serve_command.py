"""Tests for ServeCommand.resolve_host_port().

Priority chain under test:
  CLI --host/--port  >  APP_HOST/APP_PORT (fastapi.host/port)
  >  APP_URL (fastapi.app_url)  >  built-in defaults (127.0.0.1, 8000).

``resolve_host_port`` is tested in isolation — no uvicorn, no real Application
required.  We patch :func:`fastapi_startkit.Config.get` and stub the Cleo
option bag so we can drive every combination without IO.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi_startkit.fastapi.commands.serve_command import ServeCommand

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_command(cli_host: str | None = None, cli_port: str | None = None) -> ServeCommand:
    """Return a ServeCommand whose ``option()`` returns the given CLI values."""
    cmd = ServeCommand.__new__(ServeCommand)

    def _option(name):
        if name == "host":
            return cli_host
        if name == "port":
            return cli_port
        return None

    cmd.option = _option  # type: ignore[method-assign]
    return cmd


def config_get(config: dict):
    """Return a side_effect for ``Config.get`` driven by *config*."""

    def _get(key, default=None):
        return config.get(key, default)

    return _get


# ---------------------------------------------------------------------------
# 1. Default fallback — nothing set anywhere
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_host_and_port(self):
        cmd = make_command()
        cfg = {}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == _DEFAULT_HOST
        assert port == _DEFAULT_PORT


# ---------------------------------------------------------------------------
# 2. APP_URL only
# ---------------------------------------------------------------------------


class TestAppUrl:
    def test_app_url_host_and_port_extracted(self):
        cmd = make_command()
        cfg = {"fastapi.app_url": "http://myapp.com:9000"}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "myapp.com"
        assert port == 9000

    def test_app_url_no_port_falls_back_to_default_port(self):
        """APP_URL with no port component → default port 8000."""
        cmd = make_command()
        cfg = {"fastapi.app_url": "http://myapp.com"}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "myapp.com"
        assert port == _DEFAULT_PORT

    def test_app_url_bare_host_with_scheme_omitted(self):
        """``myapp.com:9000`` (no scheme) is normalised before parsing."""
        cmd = make_command()
        cfg = {"fastapi.app_url": "myapp.com:9000"}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "myapp.com"
        assert port == 9000

    def test_app_url_no_host_falls_back_to_default_host(self):
        """An APP_URL that resolves to an empty hostname keeps the default host."""
        cmd = make_command()
        # An empty APP_URL string → treated as "not set"
        cfg = {"fastapi.app_url": ""}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == _DEFAULT_HOST
        assert port == _DEFAULT_PORT


# ---------------------------------------------------------------------------
# 3. APP_HOST / APP_PORT override APP_URL
# ---------------------------------------------------------------------------


class TestEnvOverridesAppUrl:
    def test_app_host_overrides_app_url_host(self):
        cmd = make_command()
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.host": "0.0.0.0",
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "0.0.0.0"
        assert port == 9000  # port still from APP_URL

    def test_app_port_overrides_app_url_port(self):
        cmd = make_command()
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.port": 5000,
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "myapp.com"
        assert port == 5000  # port overridden

    def test_app_host_and_port_both_override_app_url(self):
        cmd = make_command()
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.host": "0.0.0.0",
            "fastapi.port": 5000,
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "0.0.0.0"
        assert port == 5000


# ---------------------------------------------------------------------------
# 4. CLI flags override everything
# ---------------------------------------------------------------------------


class TestCliOverridesAll:
    def test_cli_host_overrides_app_url_and_env(self):
        cmd = make_command(cli_host="localhost")
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.host": "0.0.0.0",
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "localhost"
        assert port == 9000

    def test_cli_port_overrides_app_url_and_env(self):
        cmd = make_command(cli_port="3000")
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.port": 5000,
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "myapp.com"
        assert port == 3000

    def test_cli_host_and_port_override_everything(self):
        cmd = make_command(cli_host="localhost", cli_port="3000")
        cfg = {
            "fastapi.app_url": "http://myapp.com:9000",
            "fastapi.host": "0.0.0.0",
            "fastapi.port": 5000,
        }
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "localhost"
        assert port == 3000

    def test_cli_host_with_no_app_url(self):
        """CLI --host works even when APP_URL is not configured."""
        cmd = make_command(cli_host="0.0.0.0")
        cfg = {}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == "0.0.0.0"
        assert port == _DEFAULT_PORT

    def test_cli_port_with_no_app_url(self):
        """CLI --port works even when APP_URL is not configured."""
        cmd = make_command(cli_port="9999")
        cfg = {}
        with patch("fastapi_startkit.configuration.config.Config.get", side_effect=config_get(cfg)):
            host, port = cmd.resolve_host_port()
        assert host == _DEFAULT_HOST
        assert port == 9999


# ---------------------------------------------------------------------------
# 5. FastAPIConfig dataclass — field defaults
# ---------------------------------------------------------------------------


class TestFastAPIConfigDefaults:
    def test_host_defaults_to_empty_string_when_no_env(self):
        """Config host/port default to empty/zero so they don't mask APP_URL."""
        import os

        from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig

        env_backup = {k: os.environ.pop(k) for k in ("APP_HOST", "APP_PORT", "APP_URL") if k in os.environ}
        try:
            cfg = FastAPIConfig()
            assert cfg.host == ""
            assert cfg.port == 0
            assert cfg.app_url == ""
        finally:
            os.environ.update(env_backup)

    def test_host_reads_from_app_host_env(self):
        import os

        from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig

        env_backup = {k: os.environ.pop(k) for k in ("APP_HOST", "APP_PORT", "APP_URL") if k in os.environ}
        try:
            os.environ["APP_HOST"] = "10.0.0.1"
            cfg = FastAPIConfig()
            assert cfg.host == "10.0.0.1"
        finally:
            os.environ.update(env_backup)
            os.environ.pop("APP_HOST", None)

    def test_port_reads_from_app_port_env(self):
        import os

        from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig

        env_backup = {k: os.environ.pop(k) for k in ("APP_HOST", "APP_PORT", "APP_URL") if k in os.environ}
        try:
            os.environ["APP_PORT"] = "9001"
            cfg = FastAPIConfig()
            assert cfg.port == 9001
        finally:
            os.environ.update(env_backup)
            os.environ.pop("APP_PORT", None)

    def test_app_url_reads_from_app_url_env(self):
        import os

        from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig

        env_backup = {k: os.environ.pop(k) for k in ("APP_HOST", "APP_PORT", "APP_URL") if k in os.environ}
        try:
            os.environ["APP_URL"] = "http://staging.myapp.com:7000"
            cfg = FastAPIConfig()
            assert cfg.app_url == "http://staging.myapp.com:7000"
        finally:
            os.environ.update(env_backup)
            os.environ.pop("APP_URL", None)
