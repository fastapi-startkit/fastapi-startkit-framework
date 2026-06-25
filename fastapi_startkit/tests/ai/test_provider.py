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

    def test_register_merges_ai_config_into_config_store(self):
        """register() merges the resolved AIConfig into the config store under 'ai'."""
        fake_config = MagicMock()
        fake_app = MagicMock()
        fake_app.make.return_value = fake_config

        provider = AIProvider(fake_app)
        provider.register()

        fake_app.make.assert_called_with("config")
        fake_config.merge_with.assert_called_once()
        path, source = fake_config.merge_with.call_args[0]
        self.assertEqual(path, "ai")
        self.assertEqual(source["default"], AIConfig().default)

    def test_register_does_not_raise(self):
        fake_app = MagicMock()
        provider = AIProvider(fake_app)

        provider.register()

    def test_boot_does_not_raise(self):
        fake_app = MagicMock()
        provider = AIProvider(fake_app)

        provider.boot()

    def test_register_and_boot_expose_ai_config(self):
        """Full integration: after AIProvider registers, Config.get('ai') exposes AI config data."""
        from fastapi_startkit.application import Application
        from fastapi_startkit.configuration.config import Config

        app = Application()

        provider = AIProvider(app)
        provider.register()
        provider.boot()

        ai = Config.get("ai")
        self.assertIsNotNone(ai)
        self.assertEqual(ai["default"], AIConfig().default)
        self.assertIn("providers", ai)
