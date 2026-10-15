from __future__ import annotations

import os

from fastapi_startkit.configuration import Config

from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class AnthropicConfig(Config):
    """Configuration for the Anthropic provider."""

    driver: str = "anthropic"
    key: str = env("ANTHROPIC_API_KEY", "", cast=False)
    url: str = env("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    models: dict[str, str] = field(
        default_factory=lambda: {
            "default": "claude-sonnet-4-6",
        }
    )


@dataclass
class OpenAIConfig(Config):
    """Configuration for the OpenAI provider."""

    driver: str = "openai"
    key: str = env("OPENAI_API_KEY", "", cast=False)
    url: str = env("OPENAI_BASE_URL", "https://api.openai.com/v1")

    models: dict[str, str] = field(
        default_factory=lambda: {
            "default": "gpt-4o",
            "default_image": "dall-e-3",
        }
    )


@dataclass
class GoogleConfig(Config):
    """Configuration for the Google / Gemini provider."""

    driver: str = "google"
    key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "")

    models: dict[str, str] = field(
        default_factory=lambda: {
            "default": "gemini-2.5-flash-lite",
            "default_image": "imagen-3.0-generate-002",
        }
    )


@dataclass
class ElevenLabsConfig(Config):
    """Configuration for the ElevenLabs provider."""

    driver: str = "elevenlabs"
    key: str = env("ELEVENLABS_API_KEY", "", cast=False)

    models: dict[str, str] = field(
        default_factory=lambda: {
            "default_audio": "eleven_multilingual_v2",
            "default_transcribe": "scribe_v1",
        }
    )
