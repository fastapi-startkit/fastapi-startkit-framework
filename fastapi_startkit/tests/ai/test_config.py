"""Tests for AI configuration dataclasses."""

import os
import unittest
from unittest import mock

from fastapi_startkit.ai import AIConfig, AnthropicConfig, GoogleConfig, OpenAIConfig


class TestAIConfiguration(unittest.TestCase):
    def _patch_env(self, set_=None, unset=()):
        patcher = mock.patch.dict(os.environ, set_ or {})
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in unset:
            os.environ.pop(key, None)

    def test_aiconfig_default_provider_is_google(self):
        self._patch_env(unset=["AI_PROVIDER"])
        self.assertEqual(AIConfig().default, "google")

    def test_aiconfig_default_reads_ai_provider_env(self):
        self._patch_env({"AI_PROVIDER": "anthropic"})
        self.assertEqual(AIConfig().default, "anthropic")

    def test_aiconfig_providers_has_anthropic_key(self):
        self.assertIn("anthropic", AIConfig().providers)

    def test_aiconfig_providers_has_openai_key(self):
        self.assertIn("openai", AIConfig().providers)

    def test_aiconfig_providers_has_google_key(self):
        self.assertIn("google", AIConfig().providers)

    def test_aiconfig_providers_anthropic_is_instance(self):
        self.assertIsInstance(AIConfig().providers["anthropic"], AnthropicConfig)

    def test_aiconfig_providers_openai_is_instance(self):
        self.assertIsInstance(AIConfig().providers["openai"], OpenAIConfig)

    def test_aiconfig_providers_google_is_instance(self):
        self.assertIsInstance(AIConfig().providers["google"], GoogleConfig)

    def test_anthropic_config_driver_is_anthropic(self):
        self.assertEqual(AnthropicConfig().driver, "anthropic")

    def test_anthropic_config_picks_up_api_key_from_env(self):
        self._patch_env({"ANTHROPIC_API_KEY": "test-anthropic-key-123"})
        self.assertEqual(AnthropicConfig().key, "test-anthropic-key-123")

    def test_anthropic_config_key_defaults_to_empty_when_env_not_set(self):
        self._patch_env(unset=["ANTHROPIC_API_KEY"])
        self.assertEqual(AnthropicConfig().key, "")

    def test_anthropic_config_url_default(self):
        self.assertEqual(AnthropicConfig().url, "https://api.anthropic.com")

    def test_anthropic_config_url_can_be_overridden(self):
        self._patch_env({"ANTHROPIC_BASE_URL": "https://my-proxy.example.com"})
        self.assertEqual(AnthropicConfig().url, "https://my-proxy.example.com")

    def test_openai_config_driver_is_openai(self):
        self.assertEqual(OpenAIConfig().driver, "openai")

    def test_openai_config_picks_up_api_key_from_env(self):
        self._patch_env({"OPENAI_API_KEY": "sk-openai-test-key"})
        self.assertEqual(OpenAIConfig().key, "sk-openai-test-key")

    def test_openai_config_key_defaults_to_empty_when_env_not_set(self):
        self._patch_env(unset=["OPENAI_API_KEY"])
        self.assertEqual(OpenAIConfig().key, "")

    def test_openai_config_url_default(self):
        self.assertEqual(OpenAIConfig().url, "https://api.openai.com/v1")

    def test_openai_config_url_can_be_overridden(self):
        self._patch_env({"OPENAI_BASE_URL": "https://openai-proxy.example.com/v1"})
        self.assertEqual(OpenAIConfig().url, "https://openai-proxy.example.com/v1")

    def test_google_config_driver_is_google(self):
        self.assertEqual(GoogleConfig().driver, "google")

    def test_google_config_picks_up_gemini_api_key(self):
        self._patch_env({"GEMINI_API_KEY": "gemini-key-abc"}, unset=["GOOGLE_API_KEY"])
        self.assertEqual(GoogleConfig().key, "gemini-key-abc")

    def test_google_config_falls_back_to_google_api_key(self):
        self._patch_env({"GOOGLE_API_KEY": "google-api-fallback"}, unset=["GEMINI_API_KEY"])
        self.assertEqual(GoogleConfig().key, "google-api-fallback")

    def test_google_config_gemini_key_takes_precedence(self):
        self._patch_env({"GEMINI_API_KEY": "gemini-wins", "GOOGLE_API_KEY": "google-loses"})
        self.assertEqual(GoogleConfig().key, "gemini-wins")

    def test_google_config_key_defaults_to_empty_when_neither_set(self):
        self._patch_env(unset=["GEMINI_API_KEY", "GOOGLE_API_KEY"])
        self.assertEqual(GoogleConfig().key, "")
