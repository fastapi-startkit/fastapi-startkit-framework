"""Tests for FastAPIConfig raw values."""

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
