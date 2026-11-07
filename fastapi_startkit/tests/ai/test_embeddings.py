import math
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fastapi_startkit.ai import Ai, AIConfig, Embeddings, EmbeddingsFake, EmbeddingsPrompt, EmbeddingsResponse
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


def test_prompt_contains_matches_substrings_of_any_input():
    prompt = EmbeddingsPrompt(["Napa Valley has great wine.", "Laravel is a PHP framework."], None, "openai", "m")

    assert prompt.contains("Valley")
    assert prompt.contains("PHP framework")
    assert not prompt.contains("Django")


def test_prompt_contains_is_false_without_inputs():
    assert not EmbeddingsPrompt([], None, "openai", "m").contains("anything")


def test_response_first_returns_the_first_vector():
    response = EmbeddingsResponse([[1.0, 0.0], [0.0, 1.0]], "openai", "m")

    assert response.first() == [1.0, 0.0]


def test_fake_embedding_is_a_unit_vector_of_the_given_size():
    vector = Embeddings.fake_embedding(64)

    assert len(vector) == 64
    assert math.isclose(math.sqrt(sum(value * value for value in vector)), 1.0)


def test_fake_embedding_defaults_to_1536_dimensions():
    assert len(Embeddings.fake_embedding()) == 1536


def test_fake_embedding_vectors_differ():
    assert Embeddings.fake_embedding(16) != Embeddings.fake_embedding(16)


def test_embeddings_fake_records_prompts_in_order():
    fake = EmbeddingsFake()
    first = EmbeddingsPrompt(["a"], 2, "openai", "m")
    second = EmbeddingsPrompt(["b", "c"], 3, "openai", "m")

    assert len(fake.respond(first)[0]) == 2
    assert [len(vector) for vector in fake.respond(second)] == [3, 3]
    assert fake.prompts == [first, second]


def test_embeddings_fake_returns_no_vectors_for_no_inputs():
    assert EmbeddingsFake().respond(EmbeddingsPrompt([], None, "openai", "m")) == []


def test_embeddings_fake_callable_wins_over_prevent_stray():
    fake = EmbeddingsFake(lambda prompt: [[0.5]] * len(prompt.inputs)).prevent_stray_embeddings()

    assert fake.respond(EmbeddingsPrompt(["a", "b"], None, "openai", "m")) == [[0.5], [0.5]]


def test_prevent_stray_without_responses_raises_on_first_call():
    fake = EmbeddingsFake().prevent_stray_embeddings()

    with pytest.raises(RuntimeError, match=r"\['a'\]"):
        fake.respond(EmbeddingsPrompt(["a"], None, "openai", "m"))
    assert len(fake.prompts) == 1


def test_prevent_stray_embeddings_returns_the_fake():
    fake = EmbeddingsFake()

    assert fake.prevent_stray_embeddings() is fake


def test_listed_responses_are_copied():
    responses = [[[1.0]]]
    fake = EmbeddingsFake(responses)

    fake.respond(EmbeddingsPrompt(["a"], None, "openai", "m"))

    assert responses == [[[1.0]]]


async def test_fake_replaces_the_previous_fake():
    Embeddings.fake()
    await Embeddings.of(["old"]).generate()

    Embeddings.fake()

    Embeddings.assert_nothing_generated()


async def test_reset_fake_sends_calls_to_the_provider_again(init_embeddings):
    Embeddings.fake()
    Embeddings.reset_fake()

    response = await Embeddings.of(["a", "b"]).generate()

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
    init_embeddings.assert_called_once()
    with pytest.raises(RuntimeError, match="not faked"):
        Embeddings.assert_nothing_generated()


async def test_fake_records_resolved_provider_model_and_dimensions():
    fake = Embeddings.fake()

    await Embeddings.of(["a"]).dimensions(32).generate("bedrock")
    await Embeddings.of(["b"]).generate(model="text-embedding-3-large")

    assert fake.prompts == [
        EmbeddingsPrompt(["a"], 32, "bedrock", "amazon.titan-embed-text-v2:0"),
        EmbeddingsPrompt(["b"], None, "openai", "text-embedding-3-large"),
    ]


async def test_default_provider_follows_config(ai_config):
    ai_config.default_embeddings = "google"
    app().make("config").set("ai", ai_config)
    Embeddings.fake()

    response = await Embeddings.of(["a"]).generate()

    assert (response.provider, response.model) == ("google", "gemini-embedding-001")


async def test_builder_copies_inputs():
    inputs = ["a"]
    builder = Embeddings.of(inputs)
    inputs.append("b")
    fake = Embeddings.fake()

    await builder.generate()

    assert fake.prompts[0].inputs == ["a"]


def test_dimensions_returns_the_builder():
    builder = Embeddings.of(["a"])

    assert builder.dimensions(8) is builder


async def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        await Embeddings.of(["a"]).generate("nope")


async def test_assert_not_generated_passes_with_no_prompts():
    Embeddings.fake()

    Embeddings.assert_not_generated("anything")
    with pytest.raises(AssertionError, match="Expected embeddings matching 'anything'"):
        Embeddings.assert_generated("anything")


async def test_ai_reset_fakes_clears_the_embeddings_fake(init_embeddings):
    Embeddings.fake()
    Ai.reset_fakes()

    response = await Embeddings.of(["hello"]).generate()

    assert response.embeddings == [[0.1, 0.2], [0.3, 0.4]]
