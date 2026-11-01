from fastapi_startkit.configuration import Config
from dataclasses import dataclass, field

from fastapi_startkit.environment import env

from fastapi_startkit.ai import AnthropicConfig, BedrockConfig, ElevenLabsConfig, GoogleConfig, OpenAIConfig


@dataclass
class AIConfig(Config):
    """Top-level AI configuration — selects the default provider per modality and holds per-provider configs."""

    default: str = env("AI_PROVIDER", "google")
    default_image: str = env("AI_DEFAULT_IMAGE_PROVIDER", "openai")
    default_audio: str = env("AI_DEFAULT_AUDIO_PROVIDER", "openai")
    default_transcribe: str = env("AI_DEFAULT_TRANSCRIBE_PROVIDER", "openai")
    default_embeddings: str = env("AI_DEFAULT_EMBEDDINGS_PROVIDER", "openai")

    providers: dict[str, Config] = field(
        default_factory=lambda: {
            "google": GoogleConfig(),
            "openai": OpenAIConfig(),
            "anthropic": AnthropicConfig(),
            "elevenlabs": ElevenLabsConfig(),
            "bedrock": BedrockConfig(),
        }
    )
