from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .lab import Lab

if TYPE_CHECKING:
    from .agent import Agent


class ModelBuilder:
    # Keyed by agent class name (see _key()) so a fake can be registered
    # before any instance of that agent exists. get_model_for() consults
    # this registry, so a faked agent runs through the same message-building
    # / pipeline / tool-execution path as a real one — only the model at the
    # bottom is swapped for a deterministic stand-in.
    fake_models: dict[str, Any] = {}
    # Reserved for response-level fakes (mirroring fake_models, but for
    # cached final replies rather than whole chat models). Not yet wired up.
    fake_responses: dict[str, Any] = {}

    def __init__(self, agent: "Agent") -> None:
        self._agent = agent

    @staticmethod
    def _key(agent: "Agent | str") -> str:
        return agent if isinstance(agent, str) else type(agent).__name__

    @classmethod
    def fake(cls, agent: "Agent | str", messages: list) -> Any:
        """Register a deterministic stand-in chat model for ``agent``.

        Replays ``messages`` in order via a GenericFakeChatModel — no live
        LLM call. Plain strings are coerced into ``AIMessage(content=...)``.
        """
        from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
        from langchain_core.messages import AIMessage

        turns = [message if hasattr(message, "content") else AIMessage(content=str(message)) for message in messages]
        model = GenericFakeChatModel(messages=iter(turns))
        cls.fake_models[cls._key(agent)] = model
        return model

    @classmethod
    def has_fake_model_for(cls, agent: "Agent | str") -> bool:
        return cls._key(agent) in cls.fake_models

    @classmethod
    def get_fake_model_for(cls, agent: "Agent | str") -> Any:
        return cls.fake_models[cls._key(agent)]

    @classmethod
    def reset_fakes(cls) -> None:
        cls.fake_models.clear()
        cls.fake_responses.clear()

    def get_model_for(self, model: str | None = None, provider_options: dict | None = None) -> Any:
        """Resolve the model to run: a registered fake if one exists for
        this builder's agent, otherwise a freshly-built provider model."""
        if self.has_fake_model_for(self._agent):
            return self.get_fake_model_for(self._agent)
        return self.build(model, provider_options)

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
