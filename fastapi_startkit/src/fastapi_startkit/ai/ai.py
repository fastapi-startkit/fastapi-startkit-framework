from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .lab import Lab

if TYPE_CHECKING:
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from .agent import Agent


class Ai:
    _fakes: dict[str, GenericFakeChatModel] = {}

    def __init__(self) -> None:
        pass

    @staticmethod
    def _key(agent: "Agent | str") -> str:
        return agent if isinstance(agent, str) else type(agent).__name__

    @classmethod
    def fake(cls, agent: "Agent | str", messages: list) -> Any:
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage

        turns = [message if hasattr(message, "content") else AIMessage(content=str(message)) for message in messages]
        model = GenericFakeChatModel(messages=iter(turns))
        cls._fakes[cls._key(agent)] = model
        return model

    @classmethod
    def has_fake_model_for(cls, agent: "Agent | str") -> bool:
        return cls._key(agent) in cls._fakes

    @classmethod
    def get_fake_model_for(cls, agent: "Agent | str") -> Any:
        return cls._fakes[cls._key(agent)]

    @classmethod
    def forget(cls, agent: "Agent | str") -> None:
        cls._fakes.pop(cls._key(agent), None)

    @classmethod
    def reset_fakes(cls) -> None:
        cls._fakes.clear()

    def get_model_for(
        self,
        agent: "Agent",
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> Any:
        if self.has_fake_model_for(agent):
            return self.get_fake_model_for(agent)
        return self.build(agent, model, provider_options)

    def build(
        self,
        agent: "Agent",
        model: str | None = None,
        provider_options: dict | None = None,
    ) -> Any:
        from langchain.chat_models import init_chat_model  # noqa: PLC0415

        lab = Lab.get_provider(agent.provider)
        kwargs: dict[str, Any] = {"model_provider": lab.get_provider_key()}

        api_key = lab.get_api_key()
        if api_key:
            kwargs["api_key"] = api_key
        if agent.max_tokens:
            kwargs["max_tokens"] = agent.max_tokens
        if agent.top_p != 1.0:
            kwargs["top_p"] = agent.top_p
        if agent.timeout:
            kwargs["timeout"] = agent.timeout

        kwargs.update(self._resolve_provider_options(agent, provider_options))

        chat_model = init_chat_model(self._resolve_model(agent, model), **kwargs)

        tools = list(agent.tools())
        chat_model = chat_model.bind_tools(tools) if tools else chat_model

        schema = agent.schema()
        if schema is not None:
            chat_model = chat_model.with_structured_output(schema, include_raw=True)

        return chat_model

    def _resolve_model(self, agent: "Agent", override: str | None = None) -> str:
        return Lab.get_provider(agent.provider).get_model(override or agent.model or None)

    def _resolve_provider_options(self, agent: "Agent", override: dict | None = None) -> dict:
        options = dict(agent.provider_options().get(agent.provider, {}))
        if override:
            provider_specific = override.get(agent.provider, override)
            if isinstance(provider_specific, dict):
                options.update(provider_specific)
        return options
