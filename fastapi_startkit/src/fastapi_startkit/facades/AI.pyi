from fastapi_startkit.ai import AIConfig

class AI:
    """Facade for accessing the AI configuration registered under the 'ai' key."""

    @staticmethod
    def config() -> AIConfig:
        """Return the full AIConfig object."""
        ...

    @staticmethod
    def default() -> str:
        """Return the default AI provider name."""
        ...

    @staticmethod
    def providers() -> dict:
        """Return the configured provider configs (OpenAIConfig, AnthropicConfig, GoogleConfig)."""
        ...
