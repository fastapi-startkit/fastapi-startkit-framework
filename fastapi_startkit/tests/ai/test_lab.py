"""Lab resolves the active provider, model, and LangChain model URL from config."""

import pytest

from fastapi_startkit.ai import AIConfig
from fastapi_startkit.ai.lab import Lab, ModelType
from fastapi_startkit.application import app


@pytest.fixture
def ai_config():
    container = app()
    container.bind("ai", AIConfig())
    container.make("config").set("ai", AIConfig())
    return container


def test_provider_key_maps_google_to_genai():
    assert Lab.GOOGLE.get_provider_key() == "google_genai"
    assert Lab.OPENAI.get_provider_key() == "openai"
    assert Lab.ANTHROPIC.get_provider_key() == "anthropic"
    assert Lab.ELEVENLABS.get_provider_key() == "elevenlabs"


def test_get_model_returns_explicit_override():
    # No config needed — an explicit model short-circuits the lookup.
    assert Lab.GOOGLE.get_model("custom-model") == "custom-model"


def test_get_model_text_default(ai_config):
    assert Lab.GOOGLE.get_model() == "gemini-2.0-flash"
    assert Lab.ANTHROPIC.get_model() == "claude-sonnet-4-6"
    assert Lab.OPENAI.get_model() == "gpt-4o"


def test_get_model_image_default(ai_config):
    assert Lab.OPENAI.get_model(model_type=ModelType.IMAGE) == "dall-e-3"
    assert Lab.GOOGLE.get_model(model_type=ModelType.IMAGE) == "imagen-3.0-generate-002"


def test_get_provider_uses_config_default(ai_config):
    assert Lab.get_provider().value == "google"


def test_get_provider_explicit_wins():
    assert Lab.get_provider("anthropic") is Lab.ANTHROPIC


def test_get_model_url_text(ai_config):
    assert Lab.get_model_url() == "google_genai:gemini-2.0-flash"
    assert Lab.get_model_url("anthropic") == "anthropic:claude-sonnet-4-6"
