from dataclasses import dataclass, field

from fastapi_startkit.environment import env


@dataclass
class OpenAIConfig:
    driver: str = "openai"
    key: str = field(default_factory=lambda: env("OPENAI_API_KEY", ""))
    url: str = field(
        default_factory=lambda: env("OPENAI_BASE_URL", "https://api.openai.com/v1")
    )


@dataclass
class AnthropicConfig:
    driver: str = "anthropic"
    key: str = field(default_factory=lambda: env("ANTHROPIC_API_KEY", ""))
    url: str = field(
        default_factory=lambda: env("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    )


@dataclass
class GoogleConfig:
    driver: str = "google"
    key: str = field(
        default_factory=lambda: env("GEMINI_API_KEY", "") or env("GOOGLE_API_KEY", "")
    )


@dataclass
class AIConfig:
    default: str = field(default_factory=lambda: env("AI_PROVIDER", "google"))

    providers: dict = field(
        default_factory=lambda: {
            "openai": OpenAIConfig(),
            "anthropic": AnthropicConfig(),
            "google": GoogleConfig(),
        }
    )
