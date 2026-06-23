"""Tests for AIProvider service provider."""

from unittest.mock import MagicMock

from fastapi_startkit.ai import AIConfig
from fastapi_startkit.ai.providers.ai_provider import AIProvider
from fastapi_startkit.providers import Provider


# ─── AIProvider class contract ────────────────────────────────────────────────


def test_ai_provider_is_a_provider():
    assert issubclass(AIProvider, Provider)


def test_ai_provider_key():
    assert AIProvider.provider_key == "ai"


# ─── AIProvider.register() ────────────────────────────────────────────────────


def test_register_binds_ai_config_to_container():
    """register() must call app.bind('ai', <AIConfig instance>)."""
    fake_app = MagicMock()
    provider = AIProvider(fake_app)

    provider.register()

    fake_app.bind.assert_called_once()
    call_args = fake_app.bind.call_args
    assert call_args[0][0] == "ai"
    assert isinstance(call_args[0][1], AIConfig)


def test_register_does_not_raise():
    fake_app = MagicMock()
    provider = AIProvider(fake_app)

    # Should not raise any exception
    provider.register()


# ─── AIProvider.boot() ────────────────────────────────────────────────────────


def test_boot_sets_ai_in_config_store():
    """boot() must call config.set('ai', <AIConfig>) so Config.get('ai') works."""
    ai_config_instance = AIConfig()

    fake_config_store = MagicMock()
    fake_app = MagicMock()
    fake_app.make.side_effect = lambda key: ai_config_instance if key == "ai" else fake_config_store

    provider = AIProvider(fake_app)
    provider.boot()

    # Verify config store received the AIConfig under the 'ai' key
    fake_config_store.set.assert_called_once_with("ai", ai_config_instance)


def test_boot_does_not_raise():
    ai_config_instance = AIConfig()
    fake_config_store = MagicMock()
    fake_app = MagicMock()
    fake_app.make.side_effect = lambda key: ai_config_instance if key == "ai" else fake_config_store

    provider = AIProvider(fake_app)
    provider.boot()  # must not raise


# ─── Integration: Config.get('ai') after boot ─────────────────────────────────


def test_config_get_ai_returns_ai_config_data_after_provider_boots():
    """Full integration: after AIProvider boots, Config.get('ai') exposes AI config data.

    The framework's Configuration.set() serialises dataclasses to a dotty-dict, so
    Config.get('ai') returns a mapping rather than an AIConfig instance.  The test
    verifies the 'default' key is present and the raw container binding stays typed.
    """
    from fastapi_startkit.application import Application
    from fastapi_startkit.configuration.config import Config

    # Use the test Application singleton (initialised by the session fixture)
    app = Application()

    ai_config_instance = AIConfig()

    # Simulate what AIProvider.register() does
    app.bind("ai", ai_config_instance)

    # Simulate what AIProvider.boot() does — config.set() serialises the dataclass
    app.make("config").set("ai", ai_config_instance)

    # Config.get('ai') returns the serialised dict structure
    result = Config.get("ai")
    assert result is not None
    # The 'default' field must survive serialisation
    assert result["default"] == ai_config_instance.default

    # The raw container binding retains the typed AIConfig instance
    assert isinstance(app.make("ai"), AIConfig)


def test_ai_provider_register_and_boot_together():
    """register() followed by boot() produces an AIConfig in the container."""
    from fastapi_startkit.application import Application

    app = Application()

    provider = AIProvider(app)
    provider.register()
    provider.boot()

    ai_value = app.make("ai")
    assert isinstance(ai_value, AIConfig)
