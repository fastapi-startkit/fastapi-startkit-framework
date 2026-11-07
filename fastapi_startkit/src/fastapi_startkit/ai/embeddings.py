from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, NamedTuple

from .lab import Lab, ModelType

Vectors = list[list[float]]
EmbeddingsResponder = Callable[["EmbeddingsPrompt"], Vectors]
PromptMatcher = str | Callable[["EmbeddingsPrompt"], bool]

DEFAULT_FAKE_DIMENSIONS = 1536


class EmbeddingsProvider(NamedTuple):
    key: str
    dimensions_option: Callable[[int], dict[str, Any]]
    accepts_api_key: bool


EMBEDDINGS_PROVIDERS: dict[Lab, EmbeddingsProvider] = {
    Lab.OPENAI: EmbeddingsProvider("openai", lambda size: {"dimensions": size}, True),
    Lab.GOOGLE: EmbeddingsProvider("google_genai", lambda size: {"output_dimensionality": size}, True),
    Lab.BEDROCK: EmbeddingsProvider("bedrock", lambda size: {"model_kwargs": {"dimensions": size}}, False),
}


@dataclass(frozen=True)
class EmbeddingsPrompt:
    inputs: list[str]
    dimensions: int | None
    provider: str
    model: str

    def contains(self, text: str) -> bool:
        return any(text in value for value in self.inputs)


@dataclass(frozen=True)
class EmbeddingsResponse:
    embeddings: Vectors
    provider: str
    model: str

    def first(self) -> list[float]:
        return self.embeddings[0]


class EmbeddingsFake:
    def __init__(self, responses: list[Vectors] | EmbeddingsResponder | None = None) -> None:
        self._responder = responses if callable(responses) else None
        self._queue = [] if callable(responses) or responses is None else list(responses)
        self._prevent_stray = False
        self.prompts: list[EmbeddingsPrompt] = []

    def prevent_stray_embeddings(self) -> EmbeddingsFake:
        self._prevent_stray = True
        return self

    def respond(self, prompt: EmbeddingsPrompt) -> Vectors:
        self.prompts.append(prompt)
        if self._responder is not None:
            return self._responder(prompt)
        if self._queue:
            return self._queue.pop(0)
        if self._prevent_stray:
            raise RuntimeError(f"No fake embeddings response defined for inputs {prompt.inputs!r}.")
        size = prompt.dimensions or DEFAULT_FAKE_DIMENSIONS
        return [Embeddings.fake_embedding(size) for _ in prompt.inputs]


class Embeddings:
    _faked: ClassVar[EmbeddingsFake | None] = None

    def __init__(self, inputs: list[str]) -> None:
        self._inputs = list(inputs)
        self._dimensions: int | None = None

    @classmethod
    def of(cls, inputs: list[str]) -> Embeddings:
        return cls(inputs)

    def dimensions(self, size: int) -> Embeddings:
        self._dimensions = size
        return self

    async def generate(self, provider: str | None = None, model: str | None = None) -> EmbeddingsResponse:
        lab = Lab.get_provider(provider, ModelType.EMBEDDINGS)
        prompt = EmbeddingsPrompt(
            inputs=self._inputs,
            dimensions=self._dimensions,
            provider=lab.value,
            model=lab.get_model(model, ModelType.EMBEDDINGS),
        )
        fake = Embeddings._faked
        embeddings = fake.respond(prompt) if fake is not None else await self._embed(lab, prompt)
        return EmbeddingsResponse(embeddings=embeddings, provider=prompt.provider, model=prompt.model)

    async def _embed(self, lab: Lab, prompt: EmbeddingsPrompt) -> Vectors:
        from langchain.embeddings import init_embeddings  # noqa: PLC0415  # pyright: ignore[reportMissingImports]

        return await init_embeddings(prompt.model, **self._options(lab, prompt)).aembed_documents(prompt.inputs)

    @staticmethod
    def _options(lab: Lab, prompt: EmbeddingsPrompt) -> dict[str, Any]:
        if lab not in EMBEDDINGS_PROVIDERS:
            supported = ", ".join(sorted(EMBEDDINGS_PROVIDERS))
            raise ValueError(f"Provider {lab.value!r} does not support embeddings. Use one of: {supported}.")
        settings = EMBEDDINGS_PROVIDERS[lab]
        options: dict[str, Any] = {"provider": settings.key, **lab.get_client_options()}
        api_key = lab.get_api_key()
        if settings.accepts_api_key and api_key:
            options["api_key"] = api_key
        if prompt.dimensions:
            options.update(settings.dimensions_option(prompt.dimensions))
        return options

    @classmethod
    def fake(cls, responses: list[Vectors] | EmbeddingsResponder | None = None) -> EmbeddingsFake:
        Embeddings._faked = EmbeddingsFake(responses)
        return Embeddings._faked

    @classmethod
    def reset_fake(cls) -> None:
        Embeddings._faked = None

    @staticmethod
    def fake_embedding(dimensions: int = DEFAULT_FAKE_DIMENSIONS) -> list[float]:
        vector = [random.gauss(0.0, 1.0) for _ in range(dimensions)]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @classmethod
    def assert_generated(cls, matcher: PromptMatcher) -> None:
        if not any(_matches(matcher, prompt) for prompt in cls._recorded()):
            raise AssertionError(f"Expected embeddings matching {matcher!r} to be generated.")

    @classmethod
    def assert_not_generated(cls, matcher: PromptMatcher) -> None:
        if any(_matches(matcher, prompt) for prompt in cls._recorded()):
            raise AssertionError(f"Unexpected embeddings matching {matcher!r} were generated.")

    @classmethod
    def assert_nothing_generated(cls) -> None:
        prompts = cls._recorded()
        if prompts:
            raise AssertionError(f"Expected no embeddings, but {len(prompts)} were generated.")

    @classmethod
    def _recorded(cls) -> list[EmbeddingsPrompt]:
        if Embeddings._faked is None:
            raise RuntimeError("Embeddings are not faked. Call Embeddings.fake() first.")
        return Embeddings._faked.prompts


def _matches(matcher: PromptMatcher, prompt: EmbeddingsPrompt) -> bool:
    return prompt.contains(matcher) if isinstance(matcher, str) else bool(matcher(prompt))
