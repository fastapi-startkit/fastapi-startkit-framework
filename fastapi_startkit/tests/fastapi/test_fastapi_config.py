"""Tests for FastAPIConfig host/port resolution (APP_HOST, APP_PORT, APP_URL)."""

import pytest

from fastapi_startkit.fastapi.config.fastapi import FastAPIConfig


class TestDefaults:
    def test_default_host(self, monkeypatch):
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_URL", raising=False)
        assert FastAPIConfig().host == "127.0.0.1"

    def test_default_port(self, monkeypatch):
        monkeypatch.delenv("APP_PORT", raising=False)
        monkeypatch.delenv("APP_URL", raising=False)
        assert FastAPIConfig().port == 8000

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


class TestExplicitEnvVars:
    def test_app_host(self, monkeypatch):
        monkeypatch.setenv("APP_HOST", "0.0.0.0")
        monkeypatch.delenv("APP_URL", raising=False)
        assert FastAPIConfig().host == "0.0.0.0"

    def test_app_port(self, monkeypatch):
        monkeypatch.setenv("APP_PORT", "9000")
        monkeypatch.delenv("APP_URL", raising=False)
        assert FastAPIConfig().port == 9000

    def test_app_reload_false(self, monkeypatch):
        monkeypatch.setenv("APP_RELOAD", "False")
        assert FastAPIConfig().reload is False


class TestAppUrlParsing:
    def test_host_and_port_from_url(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "http://myapp.com:9000")
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_PORT", raising=False)
        cfg = FastAPIConfig()
        assert cfg.host == "myapp.com"
        assert cfg.port == 9000

    def test_https_url_no_port(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "https://production.example.com")
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_PORT", raising=False)
        cfg = FastAPIConfig()
        assert cfg.host == "production.example.com"
        assert cfg.port == 8000

    def test_url_without_scheme(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "myapp.com:9000")
        monkeypatch.delenv("APP_HOST", raising=False)
        monkeypatch.delenv("APP_PORT", raising=False)
        cfg = FastAPIConfig()
        assert cfg.host == "myapp.com"
        assert cfg.port == 9000


class TestPriority:
    def test_app_host_wins_over_url(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "http://myapp.com:9000")
        monkeypatch.setenv("APP_HOST", "override.com")
        assert FastAPIConfig().host == "override.com"

    def test_app_port_wins_over_url(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "http://myapp.com:9000")
        monkeypatch.setenv("APP_PORT", "7777")
        assert FastAPIConfig().port == 7777

    def test_app_host_overrides_only_host_url_port_still_used(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "http://myapp.com:9000")
        monkeypatch.setenv("APP_HOST", "override.com")
        monkeypatch.delenv("APP_PORT", raising=False)
        cfg = FastAPIConfig()
        assert cfg.host == "override.com"
        assert cfg.port == 9000
