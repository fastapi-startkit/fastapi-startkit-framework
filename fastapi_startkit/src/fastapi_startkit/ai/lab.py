from enum import StrEnum

from fastapi_startkit import Config

CLIENT_OPTIONS: dict[str, dict[str, str]] = {
    "bedrock": {
        "region": "region_name",
        "access_key_id": "aws_access_key_id",
        "secret_access_key": "aws_secret_access_key",
        "session_token": "aws_session_token",
        "profile": "credentials_profile_name",
    },
}


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
    BEDROCK = "bedrock"

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
            "bedrock": "bedrock_converse",
        }[self.value]

    def get_client_options(self) -> dict[str, str]:
        options: dict[str, str] = {}
        for setting, option in CLIENT_OPTIONS.get(self.value, {}).items():
            value = Config.get(f"ai.providers.{self.value}.{setting}")
            if value:
                options[option] = value
        return options

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
