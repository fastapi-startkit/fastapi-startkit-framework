import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi_startkit.ai import (
    Agent,
    AIConfig,
    Classification,
    Embeddings,
    OllamaConfig,
    OpenAICompatibleConfig,
)
from fastapi_startkit.ai.classification.questions import Boolean
from fastapi_startkit.ai.lab import LabConfig, Lab
from fastapi_startkit.application import app


@pytest.fixture(autouse=True)
def ai_config():
    config = AIConfig()
    config.providers["openai"].key = "sk-test"
    config.providers["openai"].url = "https://proxy.example/v1"
    config.providers["local"] = OpenAICompatibleConfig(
        url="http://localhost:1234/v1",
        key="local-key",
        models={"default": "qwen2.5", "default_embeddings": "nomic-embed"},
    )
    config.providers["box"] = OllamaConfig(url="http://gpu-box:11434", models={"default": "llama3.1"})
    config.providers["broken"] = OpenAICompatibleConfig(driver="mistery")
    app().make("config").set("ai", config)
    yield config
    Embeddings.reset_fake()


@pytest.fixture
def init_chat_model():
    factory = MagicMock(return_value=MagicMock())
    module = ModuleType("langchain.chat_models")
    module.init_chat_model = factory  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"langchain.chat_models": module}):
        yield factory


@pytest.fixture
def init_embeddings():
    model = MagicMock()
    model.aembed_documents = AsyncMock(return_value=[[0.1, 0.2]])
    factory = MagicMock(return_value=model)
    module = ModuleType("langchain.embeddings")
    module.init_embeddings = factory  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"langchain.embeddings": module}):
        yield factory


def agent_for(name: str) -> Agent:
    agent = Agent()
    agent.provider = name
    agent.max_tokens = None
    agent.timeout = None
    return agent


def build(name: str):
    from fastapi_startkit.ai.ai import Ai

    Ai().build(agent_for(name))


def test_custom_provider_name_resolves_through_its_driver():
    provider = LabConfig.resolve("local")

    assert (provider.name, provider.driver) == ("local", Lab.OPENAI_COMPATIBLE)
    assert Lab.get_provider("box") is Lab.OLLAMA
    assert Lab.get_model_url("local") == "openai:qwen2.5"


def test_default_provider_can_be_a_custom_name():
    app().make("config").set("ai.default", "local")

    assert LabConfig.resolve() == LabConfig("local", Lab.OPENAI_COMPATIBLE)


def test_built_in_names_still_resolve():
    assert LabConfig.resolve("anthropic") == LabConfig("anthropic", Lab.ANTHROPIC)
    assert LabConfig.resolve("ollama").driver is Lab.OLLAMA


def test_unknown_driver_names_the_provider_and_driver():
    with pytest.raises(ValueError, match="AI provider 'broken' uses unknown driver 'mistery'"):
        LabConfig.resolve("broken")


def test_unconfigured_provider_raises_clear_error():
    with pytest.raises(ValueError, match="AI provider 'nope' uses unknown driver 'nope'"):
        LabConfig.resolve("nope")


def test_openai_compatible_passes_url_and_key(init_chat_model):
    build("local")

    init_chat_model.assert_called_once_with(
        "qwen2.5", model_provider="openai", api_key="local-key", base_url="http://localhost:1234/v1"
    )


def test_openai_compatible_without_key_sends_placeholder(init_chat_model):
    app().make("config").set("ai.providers.local.key", None)

    build("local")

    assert init_chat_model.call_args.kwargs["api_key"] == "not-needed"


def test_ollama_passes_base_url_without_api_key(init_chat_model):
    build("box")

    init_chat_model.assert_called_once_with("llama3.1", model_provider="ollama", base_url="http://gpu-box:11434")


def test_openai_chat_honours_base_url(init_chat_model):
    build("openai")

    init_chat_model.assert_called_once_with(
        "gpt-4o", model_provider="openai", api_key="sk-test", base_url="https://proxy.example/v1"
    )


def test_ollama_config_reads_base_url_from_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")

    assert OllamaConfig().url == "http://ollama:11434"
    assert "ollama" in AIConfig().providers


async def test_openai_compatible_embeddings_use_url_and_key(init_embeddings):
    response = await Embeddings.of(["hi"]).dimensions(64).generate("local")

    assert (response.provider, response.model) == ("local", "nomic-embed")
    init_embeddings.assert_called_once_with(
        "nomic-embed",
        provider="openai",
        check_embedding_ctx_length=False,
        base_url="http://localhost:1234/v1",
        api_key="local-key",
        dimensions=64,
    )


async def test_ollama_embeddings_use_base_url(init_embeddings):
    await Embeddings.of(["hi"]).generate("ollama")

    init_embeddings.assert_called_once_with("nomic-embed-text", provider="ollama", base_url="http://localhost:11434")


async def test_ollama_embeddings_reject_dimensions(init_embeddings):
    with pytest.raises(ValueError, match="'ollama' does not support custom embedding dimensions"):
        await Embeddings.of(["hi"]).dimensions(8).generate("ollama")


async def test_classification_runs_custom_provider_through_an_agent():
    from fastapi_startkit.ai.classification.classification import ClassificationAgent

    with ClassificationAgent.fake(['{"greeting": true}']):
        result = (
            await Classification.of("hello")
            .questions({"greeting": Boolean("Is it a greeting?")})
            .classify(provider="local")
        )

    assert (result.provider, result.model) == ("local", "qwen2.5")
