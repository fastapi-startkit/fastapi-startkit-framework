"""Tests for FastAPIConfig APP_URL / APP_HOST / APP_PORT resolution."""

import os
import importlib
import unittest.mock as mock

import pytest

# We need to reimport the module after patching env vars because the
# default_factory functions read os.environ at call-time (not import-time),
# so we can simply instantiate FastAPIConfig inside each test after patching.


def _make_config(env_vars: dict):
    """Helper: patch os.environ with *env_vars*, then instantiate FastAPIConfig."""
    # Remove keys not in env_vars so we start from a clean slate for each test.
    keys_to_clear = {"APP_HOST", "APP_PORT", "APP_URL", "APP_RELOAD"}
    patched_env = {k: v for k, v in os.environ.items() if k not in keys_to_clear}
    patched_env.update(env_vars)
    with mock.patch.dict(os.environ, patched_env, clear=True):
        # Re-import to pick up the patched env inside the helper functions.
        import fastapi_startkit.fastapi.config.fastapi as cfg_module
        importlib.reload(cfg_module)
        return cfg_module.FastAPIConfig()


# ---------------------------------------------------------------------------
# Defaults — no env vars set
# ---------------------------------------------------------------------------


class TestFastAPIConfigDefaults:
    def test_default_host(self):
        cfg = _make_config({})
        assert cfg.host == "127.0.0.1"

    def test_default_port(self):
        cfg = _make_config({})
        assert cfg.port == 8000

    def test_default_reload_excludes(self):
        cfg = _make_config({})
        assert "*.log" in cfg.reload_excludes
        assert "tests/*" in cfg.reload_excludes
        assert "node_modules/*" in cfg.reload_excludes

    def test_default_reload_dirs_is_none(self):
        cfg = _make_config({})
        assert cfg.reload_dirs is None


# ---------------------------------------------------------------------------
# Explicit APP_HOST and APP_PORT
# ---------------------------------------------------------------------------


class TestFastAPIConfigExplicitEnvVars:
    def test_app_host_is_used(self):
        cfg = _make_config({"APP_HOST": "0.0.0.0"})
        assert cfg.host == "0.0.0.0"

    def test_app_port_is_used(self):
        cfg = _make_config({"APP_PORT": "9000"})
        assert cfg.port == 9000

    def test_app_host_and_port_together(self):
        cfg = _make_config({"APP_HOST": "10.0.0.1", "APP_PORT": "5000"})
        assert cfg.host == "10.0.0.1"
        assert cfg.port == 5000


# ---------------------------------------------------------------------------
# APP_URL with host and port
# ---------------------------------------------------------------------------


class TestFastAPIConfigAppURL:
    def test_app_url_host_and_port(self):
        cfg = _make_config({"APP_URL": "http://myapp.com:9000"})
        assert cfg.host == "myapp.com"
        assert cfg.port == 9000

    def test_app_url_https_no_port(self):
        """APP_URL with https and no port → host set, port falls back to 8000."""
        cfg = _make_config({"APP_URL": "https://production.example.com"})
        assert cfg.host == "production.example.com"
        assert cfg.port == 8000

    def test_app_url_without_scheme(self):
        """APP_URL without a scheme (myapp.com:9000) is handled correctly."""
        cfg = _make_config({"APP_URL": "myapp.com:9000"})
        assert cfg.host == "myapp.com"
        assert cfg.port == 9000

    def test_app_url_plain_hostname_no_port(self):
        """APP_URL with just a hostname and no port."""
        cfg = _make_config({"APP_URL": "http://simple.example.com"})
        assert cfg.host == "simple.example.com"
        assert cfg.port == 8000


# ---------------------------------------------------------------------------
# Priority: APP_HOST / APP_PORT win over APP_URL
# ---------------------------------------------------------------------------


class TestFastAPIConfigPriority:
    def test_app_host_wins_over_app_url(self):
        cfg = _make_config({
            "APP_URL": "http://myapp.com:9000",
            "APP_HOST": "override.com",
        })
        assert cfg.host == "override.com"

    def test_app_port_wins_over_app_url(self):
        cfg = _make_config({
            "APP_URL": "http://myapp.com:9000",
            "APP_PORT": "7777",
        })
        assert cfg.port == 7777

    def test_app_host_and_port_both_win_over_app_url(self):
        cfg = _make_config({
            "APP_URL": "http://myapp.com:9000",
            "APP_HOST": "override.com",
            "APP_PORT": "1234",
        })
        assert cfg.host == "override.com"
        assert cfg.port == 1234

    def test_app_url_port_used_when_only_app_host_overrides(self):
        """APP_HOST overrides host but APP_URL port is still used for port."""
        cfg = _make_config({
            "APP_URL": "http://myapp.com:9000",
            "APP_HOST": "override.com",
        })
        # APP_PORT not set → falls through to APP_URL port
        assert cfg.port == 9000
