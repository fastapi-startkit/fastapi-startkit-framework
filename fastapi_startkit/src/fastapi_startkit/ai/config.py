"""AI configuration dataclasses for the FastAPI Startkit AI module."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class AnthropicConfig:
    """Configuration for the Anthropic provider."""

    driver: str = "anthropic"
    key: str = field(default_factory=lambda: env("ANTHROPIC_API_KEY", ""))
    url: str = field(default_factory=lambda: env("ANTHROPIC_BASE_URL", "https://api.anthropic.com"))


@dataclass
class OpenAIConfig:
    """Configuration for the OpenAI provider."""

    driver: str = "openai"
    key: str = field(default_factory=lambda: env("OPENAI_API_KEY", ""))
    url: str = field(default_factory=lambda: env("OPENAI_BASE_URL", "https://api.openai.com/v1"))


@dataclass
class GoogleConfig:
    """Configuration for the Google / Gemini provider."""

    driver: str = "google"
    key: str = field(default_factory=lambda: env("GEMINI_API_KEY", "") or env("GOOGLE_API_KEY", ""))


@dataclass
class AIConfig:
    """Top-level AI configuration — selects the default provider and holds per-provider configs."""

    default: str = field(default_factory=lambda: env("AI_PROVIDER", "google"))

    providers: dict = field(
        default_factory=lambda: {
            "openai": OpenAIConfig(),
            "anthropic": AnthropicConfig(),
            "google": GoogleConfig(),
        }
    )
