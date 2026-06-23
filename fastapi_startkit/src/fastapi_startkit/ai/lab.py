from enum import StrEnum

from fastapi_startkit import Config


class ModelType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TRANSCRIBE = "transcribe"


def _model_key(model_type: ModelType) -> str:
    """The key under a provider's ``models`` map for the given modality."""
    return "default" if model_type == ModelType.TEXT else f"default_{model_type.value}"


def _provider_field(model_type: ModelType) -> str:
    """The ``ai`` config field selecting the default provider for the given modality."""
    return "default" if model_type == ModelType.TEXT else f"default_{model_type.value}"


class Lab(StrEnum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ELEVENLABS = "elevenlabs"

    def get_api_key(self) -> str:
        """Return this provider's configured API key."""
        return Config.get(f"ai.providers.{self.value}.key")

    def get_model(self, model: str | None = None, model_type: ModelType = ModelType.TEXT) -> str:
        return model or Config.get(f"ai.providers.{self.value}.models.{_model_key(model_type)}")

    def get_provider_key(self) -> str:
        """Map this provider to its LangChain ``init_chat_model`` id."""
        return {
            "anthropic": "anthropic",
            "openai": "openai",
            "google": "google_genai",
            "elevenlabs": "elevenlabs",
        }[self.value]

    @staticmethod
    def get_provider(provider: str | None = None, model_type: ModelType = ModelType.TEXT) -> "Lab":
        """Resolve a provider name (or the configured default for the modality) to a ``Lab``."""
        provider = provider or Config.get(f"ai.{_provider_field(model_type)}")
        return Lab(provider)

    @staticmethod
    def get_model_url(
            provider: str | None = None,
            model: str | None = None,
            model_type: ModelType = ModelType.TEXT,
    ) -> str:
        """Build the ``"<langchain-provider>:<model>"`` string for ``init_chat_model``/``create_agent``."""
        lab = Lab.get_provider(provider, model_type)
        return f"{lab.get_provider_key()}:{lab.get_model(model, model_type)}"
