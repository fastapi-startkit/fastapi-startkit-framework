"""Tests for AI configuration dataclasses."""

from fastapi_startkit.ai import AIConfig, AnthropicConfig, GoogleConfig, OpenAIConfig


# ─── AIConfig defaults ────────────────────────────────────────────────────────


def test_aiconfig_default_provider_is_google(monkeypatch):
    """Default provider is 'google' when AI_PROVIDER env var is not set."""
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    config = AIConfig()
    assert config.default == "google"


def test_aiconfig_default_reads_ai_provider_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "anthropic")
    config = AIConfig()
    assert config.default == "anthropic"


def test_aiconfig_providers_has_anthropic_key():
    config = AIConfig()
    assert "anthropic" in config.providers


def test_aiconfig_providers_has_openai_key():
    config = AIConfig()
    assert "openai" in config.providers


def test_aiconfig_providers_has_google_key():
    config = AIConfig()
    assert "google" in config.providers


def test_aiconfig_providers_anthropic_is_instance():
    config = AIConfig()
    assert isinstance(config.providers["anthropic"], AnthropicConfig)


def test_aiconfig_providers_openai_is_instance():
    config = AIConfig()
    assert isinstance(config.providers["openai"], OpenAIConfig)


def test_aiconfig_providers_google_is_instance():
    config = AIConfig()
    assert isinstance(config.providers["google"], GoogleConfig)


# ─── AnthropicConfig ──────────────────────────────────────────────────────────


def test_anthropic_config_driver_is_anthropic():
    config = AnthropicConfig()
    assert config.driver == "anthropic"


def test_anthropic_config_picks_up_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key-123")
    config = AnthropicConfig()
    assert config.key == "test-anthropic-key-123"


def test_anthropic_config_key_defaults_to_empty_when_env_not_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config = AnthropicConfig()
    assert config.key == ""


def test_anthropic_config_url_default():
    config = AnthropicConfig()
    assert config.url == "https://api.anthropic.com"


def test_anthropic_config_url_can_be_overridden(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://my-proxy.example.com")
    config = AnthropicConfig()
    assert config.url == "https://my-proxy.example.com"


# ─── OpenAIConfig ─────────────────────────────────────────────────────────────


def test_openai_config_driver_is_openai():
    config = OpenAIConfig()
    assert config.driver == "openai"


def test_openai_config_picks_up_api_key_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test-key")
    config = OpenAIConfig()
    assert config.key == "sk-openai-test-key"


def test_openai_config_key_defaults_to_empty_when_env_not_set(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = OpenAIConfig()
    assert config.key == ""


def test_openai_config_url_default():
    config = OpenAIConfig()
    assert config.url == "https://api.openai.com/v1"


def test_openai_config_url_can_be_overridden(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai-proxy.example.com/v1")
    config = OpenAIConfig()
    assert config.url == "https://openai-proxy.example.com/v1"


# ─── GoogleConfig ─────────────────────────────────────────────────────────────


def test_google_config_driver_is_google():
    config = GoogleConfig()
    assert config.driver == "google"


def test_google_config_picks_up_gemini_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-abc")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = GoogleConfig()
    assert config.key == "gemini-key-abc"


def test_google_config_falls_back_to_google_api_key(monkeypatch):
    """When GEMINI_API_KEY is not set, fall back to GOOGLE_API_KEY."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "google-api-fallback")
    config = GoogleConfig()
    assert config.key == "google-api-fallback"


def test_google_config_gemini_key_takes_precedence(monkeypatch):
    """GEMINI_API_KEY wins over GOOGLE_API_KEY when both are set."""
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-wins")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-loses")
    config = GoogleConfig()
    assert config.key == "gemini-wins"


def test_google_config_key_defaults_to_empty_when_neither_set(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = GoogleConfig()
    assert config.key == ""
