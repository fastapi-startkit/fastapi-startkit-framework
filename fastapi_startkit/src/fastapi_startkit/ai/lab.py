from __future__ import annotations

from dataclasses import dataclass
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
    "openai-compatible": {"url": "base_url"},
    "ollama": {"url": "base_url"},
}

CHAT_OPTIONS: dict[str, dict[str, str]] = {
    "openai": {"url": "base_url"},
}

KEYLESS_API_KEY = "not-needed"


class ModelType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    TRANSCRIBE = "transcribe"
    EMBEDDINGS = "embeddings"
    DECISIONS = "decisions"

    @property
    def key(self) -> str:
        return {
            ModelType.TEXT: "default",
            ModelType.IMAGE: "default_image",
            ModelType.AUDIO: "default_audio",
            ModelType.TRANSCRIBE: "default_transcribe",
            ModelType.EMBEDDINGS: "default_embeddings",
            ModelType.DECISIONS: "default_decisions",
        }[self]


class Provider(StrEnum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    ELEVENLABS = "elevenlabs"
    BEDROCK = "bedrock"
    OPENAI_COMPATIBLE = "openai-compatible"
    OLLAMA = "ollama"

    def get_api_key(self) -> str:
        return ConfiguredProvider(self.value, self).get_api_key()

    def get_model(self, model: str | None = None, model_type: ModelType = ModelType.TEXT) -> str:
        return ConfiguredProvider(self.value, self).get_model(model, model_type)

    def get_provider_key(self) -> str:
        return {
            "anthropic": "anthropic",
            "openai": "openai",
            "google": "google_genai",
            "elevenlabs": "elevenlabs",
            "bedrock": "bedrock_converse",
            "openai-compatible": "openai",
            "ollama": "ollama",
        }[self.value]

    def get_client_options(self) -> dict[str, str]:
        return ConfiguredProvider(self.value, self).get_client_options()

    @staticmethod
    def get_provider(provider: str | None = None, model_type: ModelType = ModelType.TEXT) -> Provider:
        return ConfiguredProvider.resolve(provider, model_type).driver

    @staticmethod
    def get_model_url(
        provider: str | None = None,
        model: str | None = None,
        model_type: ModelType = ModelType.TEXT,
    ) -> str:
        return ConfiguredProvider.resolve(provider, model_type).get_model_url(model, model_type)


@dataclass(frozen=True)
class ConfiguredProvider:
    name: str
    driver: Provider

    @classmethod
    def resolve(cls, provider: str | None = None, model_type: ModelType = ModelType.TEXT) -> ConfiguredProvider:
        name = provider or Config.get(f"ai.{model_type.key}")
        driver = Config.get(f"ai.providers.{name}.driver") or name
        if driver not in Provider:
            drivers = ", ".join(member.value for member in Provider)
            raise ValueError(f"AI provider {name!r} uses unknown driver {driver!r}. Use one of: {drivers}.")
        return cls(name, Provider(driver))

    @property
    def value(self) -> str:
        return self.name

    def setting(self, key: str):
        return Config.get(f"ai.providers.{self.name}.{key}")

    def get_api_key(self) -> str:
        key = self.setting("key")
        if not key and self.driver is Provider.OPENAI_COMPATIBLE:
            return KEYLESS_API_KEY
        return key

    def get_model(self, model: str | None = None, model_type: ModelType = ModelType.TEXT) -> str:
        return model or self.setting(f"models.{model_type.key}")

    def get_provider_key(self) -> str:
        return self.driver.get_provider_key()

    def get_client_options(self) -> dict[str, str]:
        return self._options(CLIENT_OPTIONS)

    def get_chat_options(self) -> dict[str, str]:
        return {**self.get_client_options(), **self._options(CHAT_OPTIONS)}

    def get_model_url(self, model: str | None = None, model_type: ModelType = ModelType.TEXT) -> str:
        return f"{self.get_provider_key()}:{self.get_model(model, model_type)}"

    def _options(self, mapping: dict[str, dict[str, str]]) -> dict[str, str]:
        options: dict[str, str] = {}
        for setting, option in mapping.get(self.driver.value, {}).items():
            value = self.setting(setting)
            if value:
                options[option] = value
        return options
