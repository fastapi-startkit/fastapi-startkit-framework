from __future__ import annotations

from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class AnthropicConfig:
    """Configuration for the Anthropic provider."""

    driver: str = "anthropic"
    key: str = field(default_factory=lambda: env("ANTHROPIC_API_KEY", ""))
    url: str = field(default_factory=lambda: env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))

    models: dict = field(
        default_factory=lambda: {
            "default": "claude-sonnet-4-6",
        }
    )


@dataclass
class OpenAIConfig:
    """Configuration for the OpenAI provider."""

    driver: str = "openai"
    key: str = field(default_factory=lambda: env("OPENAI_API_KEY", ""))
    url: str = field(default_factory=lambda: env("OPENAI_BASE_URL", "https://api.openai.com/v1"))

    models: dict = field(
        default_factory=lambda: {
            "default": "gpt-4o",
            "default_image": "dall-e-3",
        }
    )


@dataclass
class GoogleConfig:
    """Configuration for the Google / Gemini provider."""

    driver: str = "google"
    key: str = field(default_factory=lambda: env("GEMINI_API_KEY", "") or env("GOOGLE_API_KEY", ""))

    models: dict = field(
        default_factory=lambda: {
            "default": "gemini-2.5-flash-lite",
            "default_image": "imagen-3.0-generate-002",
        }
    )


@dataclass
class ElevenLabsConfig:
    """Configuration for the ElevenLabs provider."""

    driver: str = "elevenlabs"
    key: str = field(default_factory=lambda: env("ELEVENLABS_API_KEY", ""))

    models: dict = field(
        default_factory=lambda: {
            "default_audio": "eleven_multilingual_v2",
            "default_transcribe": "scribe_v1",
        }
    )
