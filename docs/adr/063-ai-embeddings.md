# 063 — AI embeddings with a Laravel-style fake

- Date: 2026-11-01
- Status: Accepted

## Problem

The `ai` package covers agents, images, audio and transcription, but has no way to turn text into vectors. Apps that need semantic search or retrieval call a provider SDK by hand, so they cannot switch providers through `AIConfig` and have nothing to fake in tests. Laravel's AI SDK offers `Embeddings::for([...])->dimensions(n)->generate($provider, $model)` and an `Embeddings::fake()` with `assertGenerated`, `assertNotGenerated`, `assertNothingGenerated`, `preventStrayEmbeddings` and `fakeEmbedding`.

## Alternatives

1. **An `EmbeddingsFactory` ABC with one class per vendor SDK**, like `ImageFactory` and `AudioFactory`. Rejected: it rewrites what LangChain already ships, and chat agents already go through LangChain's `init_chat_model`.
2. **Have apps build LangChain `Embeddings` objects themselves.** Rejected: no shared config, no fake, no assertions.
3. **A context-manager fake, like `AgentFake`.** Rejected for this API: Laravel's call shape is `Embeddings::fake()` followed by static assertions, and nothing has to be entered or exited to embed.
4. **Port caching, `Str::toEmbeddings` and pgvector `whereVectorSimilarTo` at the same time.** Deferred: each is a separate feature (cache store, string helper, ORM grammar) and none is needed to generate or fake embeddings.
5. **A fluent builder over LangChain's `init_embeddings`, with a class-level fake.** Chosen.

## Decision

- `Embeddings.of(inputs).dimensions(n).generate(provider=None, model=None)` returns an `EmbeddingsResponse(embeddings, provider, model)` with `first()`. `of` replaces Laravel's `for`, which is a Python keyword; `Image.of` and `Audio.of` use the same name.
- The provider comes from `AIConfig.default_embeddings` (env `AI_DEFAULT_EMBEDDINGS_PROVIDER`, default `openai`) through a new `ModelType.EMBEDDINGS`, whose key is `default_embeddings`. Default models: OpenAI `text-embedding-3-small`, Google `gemini-embedding-001`, Bedrock `amazon.titan-embed-text-v2:0`.
- The real call is `init_embeddings(model, provider=...)` and then `aembed_documents(inputs)`. A table maps each `Lab` to its LangChain embeddings provider key and dimensions option: OpenAI `dimensions`, Google `output_dimensionality`, Bedrock `model_kwargs={"dimensions": n}`. The key from config is passed as `api_key` for OpenAI and Google. Bedrock gets `Lab.get_client_options()` (region, credentials, profile). A provider without embeddings (Anthropic, ElevenLabs) raises `ValueError`.
- Every call builds an `EmbeddingsPrompt(inputs, dimensions, provider, model)` with `contains(text)`, the same object the fake records and passes to callbacks.
- `Embeddings.fake(responses=None)` installs a class-level `EmbeddingsFake` and returns it:
  - with no responses, each input gets a random unit vector of the prompt's dimensions (1536 when unset), from `Embeddings.fake_embedding(dimensions)`;
  - a list gives one response per call, each a list of vectors; once the list runs out, calls fall back to random vectors;
  - a callable receives the `EmbeddingsPrompt` and returns the vectors.
  - `prevent_stray_embeddings()` makes a call with no queued or callable response raise `RuntimeError`.
- `Embeddings.assert_generated`, `assert_not_generated` and `assert_nothing_generated` check the recorded prompts. They accept a callable predicate or a string, which matches through `contains`. They raise `RuntimeError` when embeddings are not faked. `Embeddings.reset_fake()` removes the fake, like `Ai.reset_fakes()`.
- Laravel's queued assertions are not ported, because the package has no queued generation for any modality.

## Validation

`fastapi_startkit/tests/ai/test_embeddings.py`:

- `generate` passes the resolved provider key, model, dimension option, API key and Bedrock client options to `init_embeddings` and returns the vectors from `aembed_documents` (LangChain patched);
- the default provider and model come from `AIConfig`, and explicit arguments override them;
- an unsupported provider raises `ValueError`;
- `fake()` returns unit vectors of the requested or default dimensions, one per input;
- list responses are used in order, then fall back to random vectors;
- callable responses receive the prompt;
- `prevent_stray_embeddings` raises once responses run out;
- `assert_generated` / `assert_not_generated` / `assert_nothing_generated` pass and fail as expected with callables and strings;
- assertions without a fake raise.

`uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes with coverage at or above 80%.
