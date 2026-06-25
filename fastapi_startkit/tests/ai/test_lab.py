"""Lab resolves the active provider, model, and LangChain model URL from config."""

import unittest

from fastapi_startkit.ai import AIConfig
from fastapi_startkit.ai.lab import Lab, ModelType
from fastapi_startkit.application import app


class TestLab(unittest.TestCase):
    def setUp(self):
        container = app()
        container.bind("ai", AIConfig())
        container.make("config").set("ai", AIConfig())

    def test_provider_key_maps_google_to_genai(self):
        self.assertEqual(Lab.GOOGLE.get_provider_key(), "google_genai")
        self.assertEqual(Lab.OPENAI.get_provider_key(), "openai")
        self.assertEqual(Lab.ANTHROPIC.get_provider_key(), "anthropic")
        self.assertEqual(Lab.ELEVENLABS.get_provider_key(), "elevenlabs")

    def test_get_model_returns_explicit_override(self):
        self.assertEqual(Lab.GOOGLE.get_model("custom-model"), "custom-model")

    def test_get_model_text_default(self):
        self.assertEqual(Lab.GOOGLE.get_model(), "gemini-2.0-flash")
        self.assertEqual(Lab.ANTHROPIC.get_model(), "claude-sonnet-4-6")
        self.assertEqual(Lab.OPENAI.get_model(), "gpt-4o")

    def test_get_model_image_default(self):
        self.assertEqual(Lab.OPENAI.get_model(model_type=ModelType.IMAGE), "dall-e-3")
        self.assertEqual(Lab.GOOGLE.get_model(model_type=ModelType.IMAGE), "imagen-3.0-generate-002")

    def test_get_provider_uses_config_default(self):
        self.assertEqual(Lab.get_provider().value, "google")

    def test_get_provider_explicit_wins(self):
        self.assertIs(Lab.get_provider("anthropic"), Lab.ANTHROPIC)

    def test_get_model_url_text(self):
        self.assertEqual(Lab.get_model_url(), "google_genai:gemini-2.0-flash")
        self.assertEqual(Lab.get_model_url("anthropic"), "anthropic:claude-sonnet-4-6")
