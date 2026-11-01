import math
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi_startkit.ai import AIConfig, Embeddings, EmbeddingsPrompt
from fastapi_startkit.application import app


@pytest.fixture(autouse=True)
def ai_config():
    config = AIConfig()
    config.default_embeddings = "openai"
    config.providers["openai"].key = "sk-test"
    config.providers["google"].key = "g-test"
    config.providers["bedrock"].region = "us-east-1"
    app().make("config").set("ai", config)
    yield config
    Embeddings.reset_fake()


@pytest.fixture
def init_embeddings():
    model = MagicMock()
    model.aembed_documents = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    factory = MagicMock(return_value=model)
    module = ModuleType("langchain.embeddings")
    module.init_embeddings = factory  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"langchain.embeddings": module}):
        yield factory


async def test_generate_embeds_inputs_with_default_provider_and_model(init_embeddings):
    response = await Embeddings.of(["Napa Valley has great wine.", "Laravel is a PHP framework."]).generate()

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
    assert response.first() == [0.1, 0.2]
    assert (response.provider, response.model) == ("openai", "text-embedding-3-small")
    init_embeddings.assert_called_once_with("text-embedding-3-small", provider="openai", api_key="sk-test")
    init_embeddings.return_value.aembed_documents.assert_awaited_once_with(
        ["Napa Valley has great wine.", "Laravel is a PHP framework."]
    )


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openai", "text-embedding-3-large", {"provider": "openai", "api_key": "sk-test", "dimensions": 256}),
        (
            "google",
            "gemini-embedding-001",
            {"provider": "google_genai", "api_key": "g-test", "output_dimensionality": 256},
        ),
        (
            "bedrock",
            "amazon.titan-embed-text-v2:0",
            {"provider": "bedrock", "region_name": "us-east-1", "model_kwargs": {"dimensions": 256}},
        ),
    ],
)
async def test_generate_passes_provider_options_and_dimensions(init_embeddings, provider, model, expected):
    response = await Embeddings.of(["hello"]).dimensions(256).generate(provider, model)

    assert (response.provider, response.model) == (provider, model)
    init_embeddings.assert_called_once_with(model, **expected)


async def test_generate_omits_empty_api_key(init_embeddings, ai_config):
    ai_config.providers["openai"].key = ""
    app().make("config").set("ai", ai_config)

    await Embeddings.of(["hello"]).generate()

    init_embeddings.assert_called_once_with("text-embedding-3-small", provider="openai")


async def test_provider_without_embeddings_raises(init_embeddings):
    with pytest.raises(ValueError, match="'anthropic' does not support embeddings"):
        await Embeddings.of(["hello"]).generate("anthropic", "claude-sonnet-4-6")
    init_embeddings.assert_not_called()


async def test_fake_generates_unit_vectors_of_requested_dimensions(init_embeddings):
    Embeddings.fake()

    response = await Embeddings.of(["a", "b"]).dimensions(8).generate()
    default = await Embeddings.of(["c"]).generate()

    assert [len(vector) for vector in response.embeddings] == [8, 8]
    assert all(math.isclose(sum(value * value for value in vector), 1.0) for vector in response.embeddings)
    assert len(default.first()) == 1536
    init_embeddings.assert_not_called()


async def test_fake_uses_listed_responses_in_order_then_random_vectors():
    Embeddings.fake([[[1.0, 0.0]], [[0.0, 1.0]]])

    first = await Embeddings.of(["a"]).generate()
    second = await Embeddings.of(["b"]).generate()
    third = await Embeddings.of(["c"]).dimensions(3).generate()

    assert first.embeddings == [[1.0, 0.0]]
    assert second.embeddings == [[0.0, 1.0]]
    assert len(third.first()) == 3


async def test_fake_callable_receives_the_prompt():
    received: list[EmbeddingsPrompt] = []

    def respond(prompt: EmbeddingsPrompt):
        received.append(prompt)
        return [Embeddings.fake_embedding(prompt.dimensions or 4) for _ in prompt.inputs]

    Embeddings.fake(respond)

    response = await Embeddings.of(["a", "b"]).dimensions(4).generate("google")

    assert received == [EmbeddingsPrompt(["a", "b"], 4, "google", "gemini-embedding-001")]
    assert [len(vector) for vector in response.embeddings] == [4, 4]


async def test_prevent_stray_embeddings_raises_once_responses_run_out():
    Embeddings.fake([[[1.0]]]).prevent_stray_embeddings()

    await Embeddings.of(["a"]).generate()
    with pytest.raises(RuntimeError, match="No fake embeddings response"):
        await Embeddings.of(["b"]).generate()


async def test_generated_assertions():
    Embeddings.fake()
    Embeddings.assert_nothing_generated()

    await Embeddings.of(["Laravel is a PHP framework."]).dimensions(1536).generate()

    Embeddings.assert_generated(lambda prompt: prompt.contains("Laravel") and prompt.dimensions == 1536)
    Embeddings.assert_generated("PHP")
    Embeddings.assert_not_generated(lambda prompt: prompt.contains("Other"))
    Embeddings.assert_not_generated("Other")
    with pytest.raises(AssertionError):
        Embeddings.assert_generated("Other")
    with pytest.raises(AssertionError):
        Embeddings.assert_not_generated("Laravel")
    with pytest.raises(AssertionError):
        Embeddings.assert_nothing_generated()


def test_assertions_require_a_fake():
    with pytest.raises(RuntimeError, match="not faked"):
        Embeddings.assert_nothing_generated()
