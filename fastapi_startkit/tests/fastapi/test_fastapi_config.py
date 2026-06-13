"""Tests for FastAPIConfig raw values and _resolve_host_port priority chain."""

from fastapi_startkit.fastapi.commands.serve_command import _resolve_host_port
from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig


class TestFastAPIConfigDefaults:
    """FastAPIConfig stores raw env values — no defaults or resolution here."""

    def test_host_is_falsy_without_env(self, monkeypatch):
        monkeypatch.delenv("APP_HOST", raising=False)
        assert not FastAPIConfig().host

    def test_port_is_falsy_without_env(self, monkeypatch):
        monkeypatch.delenv("APP_PORT", raising=False)
        assert not FastAPIConfig().port

    def test_app_url_is_falsy_without_env(self, monkeypatch):
        monkeypatch.delenv("APP_URL", raising=False)
        assert not FastAPIConfig().app_url

    def test_default_reload_is_true(self, monkeypatch):
        monkeypatch.delenv("APP_RELOAD", raising=False)
        assert FastAPIConfig().reload is True

    def test_default_reload_dirs_is_none(self):
        assert FastAPIConfig().reload_dirs is None

    def test_default_reload_excludes(self):
        excludes = FastAPIConfig().reload_excludes
        assert "*.log" in excludes
        assert "tests/*" in excludes
        assert "node_modules/*" in excludes


class TestFastAPIConfigEnvVars:
    """FastAPIConfig reads raw env values without defaults."""

    def test_app_host(self, monkeypatch):
        monkeypatch.setenv("APP_HOST", "0.0.0.0")
        assert FastAPIConfig().host == "0.0.0.0"

    def test_app_port(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "9000")
        assert FastAPIConfig().port == 9000

    def test_app_url(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "http://myapp.com:9000")
        assert FastAPIConfig().app_url == "http://myapp.com:9000"

    def test_app_reload_false(self, monkeypatch):
        monkeypatch.setenv("APP_RELOAD", "False")
        assert FastAPIConfig().reload is False


class TestResolveHostPortDefaults:
    """_resolve_host_port falls back to 127.0.0.1:8000 when nothing is set."""

    def test_all_none_returns_defaults(self):
        host, port = _resolve_host_port(None, None, None)
        assert host == "127.0.0.1"
        assert port == 8000

    def test_empty_app_url_returns_defaults(self):
        host, port = _resolve_host_port(None, None, "")
        assert host == "127.0.0.1"
        assert port == 8000


class TestResolveHostPortEnvVars:
    """Env vars (APP_HOST / APP_PORT) override APP_URL and default."""

    def test_cfg_host_used(self):
        host, port = _resolve_host_port("0.0.0.0", None, None)
        assert host == "0.0.0.0"
        assert port == 8000

    def test_cfg_port_used(self):
        host, port = _resolve_host_port(None, 9000, None)
        assert host == "127.0.0.1"
        assert port == 9000

    def test_cfg_host_and_port_used(self):
        host, port = _resolve_host_port("0.0.0.0", 3000, None)
        assert host == "0.0.0.0"
        assert port == 3000


class TestResolveHostPortAppUrl:
    """APP_URL is parsed via Uri when APP_HOST / APP_PORT are not set."""

    def test_host_and_port_from_url(self):
        host, port = _resolve_host_port(None, None, "http://myapp.com:9000")
        assert host == "myapp.com"
        assert port == 9000

    def test_https_url_no_port_falls_back_to_default_port(self):
        host, port = _resolve_host_port(None, None, "https://production.example.com")
        assert host == "production.example.com"
        assert port == 8000

    def test_url_without_scheme(self):
        host, port = _resolve_host_port(None, None, "myapp.com:9000")
        assert host == "myapp.com"
        assert port == 9000

    def test_cfg_host_wins_over_url_host(self):
        host, port = _resolve_host_port("override.com", None, "http://myapp.com:9000")
        assert host == "override.com"
        assert port == 9000

    def test_cfg_port_wins_over_url_port(self):
        host, port = _resolve_host_port(None, 7777, "http://myapp.com:9000")
        assert host == "myapp.com"
        assert port == 7777

    def test_cfg_host_and_port_both_win_over_url(self):
        host, port = _resolve_host_port("override.com", 7777, "http://myapp.com:9000")
        assert host == "override.com"
        assert port == 7777


class TestResolveHostPortCliArgs:
    """CLI args override everything (highest priority)."""

    def test_cli_host_overrides_env_host(self):
        host, port = _resolve_host_port("env.com", None, None, cli_host="cli.com")
        assert host == "cli.com"

    def test_cli_port_overrides_env_port(self):
        host, port = _resolve_host_port(None, 9000, None, cli_port=1234)
        assert port == 1234

    def test_cli_overrides_app_url(self):
        host, port = _resolve_host_port(None, None, "http://myapp.com:9000", cli_host="cli.com", cli_port=1234)
        assert host == "cli.com"
        assert port == 1234

    def test_cli_overrides_default(self):
        host, port = _resolve_host_port(None, None, None, cli_host="0.0.0.0", cli_port=5000)
        assert host == "0.0.0.0"
        assert port == 5000

    def test_cli_host_only_leaves_port_from_url(self):
        host, port = _resolve_host_port(None, None, "http://myapp.com:9000", cli_host="0.0.0.0")
        assert host == "0.0.0.0"
        assert port == 9000

    def test_cli_port_only_leaves_host_from_env(self):
        host, port = _resolve_host_port("env.com", None, None, cli_port=5000)
        assert host == "env.com"
        assert port == 5000
