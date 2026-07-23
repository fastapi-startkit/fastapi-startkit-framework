from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .lab import Lab

if TYPE_CHECKING:
    from .agent import Agent


class ModelBuilder:
    def __init__(self, agent: "Agent") -> None:
        self._agent = agent

    def build(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        from langchain.chat_models import init_chat_model  # noqa: PLC0415

        lab = Lab.get_provider(self._agent.provider)
        kwargs: dict[str, Any] = {"model_provider": lab.get_provider_key()}

        api_key = lab.get_api_key()
        if api_key:
            kwargs["api_key"] = api_key
        if self._agent.max_tokens:
            kwargs["max_tokens"] = self._agent.max_tokens
        if self._agent.top_p != 1.0:
            kwargs["top_p"] = self._agent.top_p
        if self._agent.timeout:
            kwargs["timeout"] = self._agent.timeout

        kwargs.update(self._resolve_provider_options(provider_options))

        chat_model = init_chat_model(self._resolve_model(model), **kwargs)

        tools = list(self._agent.tools())
        return chat_model.bind_tools(tools) if tools else chat_model

    def _resolve_model(self, override: str | None = None) -> str:
        return Lab.get_provider(self._agent.provider).get_model(override or self._agent.model or None)

    def _resolve_provider_options(self, override: dict | None = None) -> dict:
        options = dict(self._agent.provider_options().get(self._agent.provider, {}))
        if override:
            provider_specific = override.get(self._agent.provider, override)
            if isinstance(provider_specific, dict):
                options.update(provider_specific)
        return options
