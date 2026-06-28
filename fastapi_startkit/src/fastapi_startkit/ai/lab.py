from enum import StrEnum

from fastapi_startkit import Config


class ModelType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TRANSCRIBE = "transcribe"

    @property
    def key(self) -> str:
        return {
            ModelType.TEXT: "default",
            ModelType.IMAGE: "default_image",
            ModelType.AUDIO: "default_audio",
            ModelType.TRANSCRIBE: "default_transcribe",
        }[self]


class Lab(StrEnum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ELEVENLABS = "elevenlabs"

    def get_api_key(self) -> str:
        return Config.get(f"ai.providers.{self.value}.key")

    def get_model(self, model: str | None = None, model_type: ModelType = ModelType.TEXT) -> str:
        return model or Config.get(f"ai.providers.{self.value}.models.{model_type.key}")

    def get_provider_key(self) -> str:
        return {
            "anthropic": "anthropic",
            "openai": "openai",
            "google": "google_genai",
            "elevenlabs": "elevenlabs",
        }[self.value]

    @staticmethod
    def get_provider(provider: str | None = None, model_type: ModelType = ModelType.TEXT) -> "Lab":
        provider = provider or Config.get(f"ai.{model_type.key}")
        return Lab(provider)

    @staticmethod
    def get_model_url(
        provider: str | None = None,
        model: str | None = None,
        model_type: ModelType = ModelType.TEXT,
    ) -> str:
        lab = Lab.get_provider(provider, model_type)
        return f"{lab.get_provider_key()}:{lab.get_model(model, model_type)}"
