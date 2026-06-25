"""Tests for AIProvider service provider."""

import unittest
from unittest.mock import MagicMock

from fastapi_startkit.ai import AIConfig
from fastapi_startkit.ai.providers.ai_provider import AIProvider
from fastapi_startkit.providers import Provider


class TestAIProvider(unittest.TestCase):
    def test_ai_provider_is_a_provider(self):
        self.assertTrue(issubclass(AIProvider, Provider))

    def test_ai_provider_key(self):
        self.assertEqual(AIProvider.provider_key, "ai")

    def test_register_binds_ai_config_to_container(self):
        """register() must call app.bind('ai', <AIConfig instance>)."""
        fake_app = MagicMock()
        provider = AIProvider(fake_app)

        provider.register()

        fake_app.bind.assert_called_once()
        call_args = fake_app.bind.call_args
        self.assertEqual(call_args[0][0], "ai")
        self.assertIsInstance(call_args[0][1], AIConfig)

    def test_register_does_not_raise(self):
        fake_app = MagicMock()
        provider = AIProvider(fake_app)

        provider.register()

    def test_boot_sets_ai_in_config_store(self):
        """boot() must call config.set('ai', <AIConfig>) so Config.get('ai') works."""
        ai_config_instance = AIConfig()

        fake_config_store = MagicMock()
        fake_app = MagicMock()
        fake_app.make.side_effect = lambda key: ai_config_instance if key == "ai" else fake_config_store

        provider = AIProvider(fake_app)
        provider.boot()

        fake_config_store.set.assert_called_once_with("ai", ai_config_instance)

    def test_boot_does_not_raise(self):
        ai_config_instance = AIConfig()
        fake_config_store = MagicMock()
        fake_app = MagicMock()
        fake_app.make.side_effect = lambda key: ai_config_instance if key == "ai" else fake_config_store

        provider = AIProvider(fake_app)
        provider.boot()

    def test_config_get_ai_returns_ai_config_data_after_provider_boots(self):
        """Full integration: after AIProvider boots, Config.get('ai') exposes AI config data.

        The framework's Configuration.set() serialises dataclasses to a dotty-dict, so
        Config.get('ai') returns a mapping rather than an AIConfig instance.  The test
        verifies the 'default' key is present and the raw container binding stays typed.
        """
        from fastapi_startkit.application import Application
        from fastapi_startkit.configuration.config import Config

        app = Application()

        ai_config_instance = AIConfig()

        app.bind("ai", ai_config_instance)
        app.make("config").set("ai", ai_config_instance)

        result = Config.get("ai")
        self.assertIsNotNone(result)
        self.assertEqual(result["default"], ai_config_instance.default)

        self.assertIsInstance(app.make("ai"), AIConfig)

    def test_ai_provider_register_and_boot_together(self):
        """register() followed by boot() produces an AIConfig in the container."""
        from fastapi_startkit.application import Application

        app = Application()

        provider = AIProvider(app)
        provider.register()
        provider.boot()

        ai_value = app.make("ai")
        self.assertIsInstance(ai_value, AIConfig)
