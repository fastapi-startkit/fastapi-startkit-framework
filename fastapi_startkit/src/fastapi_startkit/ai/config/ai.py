from dataclasses import dataclass, field

from fastapi_startkit.environment import env

from fastapi_startkit.ai import AnthropicConfig, ElevenLabsConfig, GoogleConfig, OpenAIConfig


@dataclass
class AIConfig:
    """Top-level AI configuration — selects the default provider per modality and holds per-provider configs."""

    default: str = field(default_factory=lambda: env("AI_PROVIDER", "google"))
    default_image: str = field(default_factory=lambda: env("AI_DEFAULT_IMAGE_PROVIDER", "openai"))
    default_audio: str = field(default_factory=lambda: env("AI_DEFAULT_AUDIO_PROVIDER", "openai"))
    default_transcribe: str = field(default_factory=lambda: env("AI_DEFAULT_TRANSCRIBE_PROVIDER", "openai"))

    providers: dict = field(
        default_factory=lambda: {
            "google": GoogleConfig(),
            "openai": OpenAIConfig(),
            "anthropic": AnthropicConfig(),
            "elevenlabs": ElevenLabsConfig(),
        }
    )
