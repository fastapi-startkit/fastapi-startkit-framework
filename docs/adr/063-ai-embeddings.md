# 063 — AI embeddings with a Laravel-style fake

- Date: 2026-11-01
- Status: Accepted

## Problem

The `ai` package covers agents, images, audio and transcription, but has no way to turn text into vectors. Apps that need semantic search or retrieval call a provider SDK by hand, so they cannot switch providers through `AIConfig` and have nothing to fake in tests. Laravel's AI SDK offers `Embeddings::for([...])->dimensions(n)->generate($provider, $model)` and an `Embeddings::fake()` with `assertGenerated`, `assertNotGenerated`, `assertNothingGenerated`, `preventStrayEmbeddings` and `fakeEmbedding`.

## Alternatives

1. **An `EmbeddingsFactory` ABC with one class per vendor SDK**, like `ImageFactory` and `AudioFactory`. Rejected: it rewrites what LangChain already ships, and chat agents already go through LangChain's `init_chat_model`.
2. **Have apps build LangChain `Embeddings` objects themselves.** Rejected: no shared config, no fake, no assertions.
3. **A context-manager fake, like `AgentFake`.** Rejected for this API: Laravel's call shape is `Embeddings::fake()` followed by static assertions, and nothing has to be entered or exited to embed.
4. **Port embedding caching.** Deferred: it needs a cache store, which the package does not have, and it is not needed to generate or fake embeddings.
5. **Accept text in the vector query methods and embed it automatically, as Laravel does.** Rejected: the query builder is synchronous and an embedding call is async. Callers run `await Str.of(text).to_embeddings()` first, and passing a `str` raises `TypeError` with that hint.
6. **Bind vectors through a pgvector-specific asyncpg codec.** Rejected: pgvector accepts the JSON text form `[0.1, 0.2]` for an untyped parameter, which is also how Laravel binds them. No driver registration is needed.
7. **A fluent builder over LangChain's `init_embeddings`, with a class-level fake.** Chosen.

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
- `Str.of(text).to_embeddings(provider=None, model=None, dimensions=None)` is an async `Stringable` method that returns one vector through `Embeddings`, so it is faked by `Embeddings.fake()`.
- pgvector columns: `table.vector(column, dimensions)` adds a `VECTOR(n)` column on PostgreSQL and raises `ValueError` on any other platform. `.index()` on a vector column creates an HNSW index with `vector_cosine_ops`. `schema.ensure_vector_extension_exists()` runs `CREATE EXTENSION IF NOT EXISTS vector`.
- Vector queries, PostgreSQL only (other grammars raise `ValueError`), using cosine distance `<=>`:
  - `select_vector_distance(column, vector, as_=None)` adds `(col <=> ?) AS col_distance`;
  - `where_vector_distance_less_than(column, vector, max_distance)` and its `or_` variant;
  - `order_by_vector_distance(column, vector)`, closest first;
  - `where_vector_similar_to(column, vector, min_similarity=0.6, order=True)` filters on `distance <= 1 - min_similarity` and orders by distance, like Laravel's `whereVectorSimilarTo`.
  The vector is bound as a JSON array of floats. The same methods are available on `Model`.
- Model fields annotated with parameterized `list[...]` or `dict[...]` (for example `embedding: list[float]`) now get `JsonCast`, as bare `list` and `dict` already did. Before this they fell back to the string cast.
- A raw `ORDER BY` that follows another order term is now separated by a comma. Before this, `order_by("a").order_by_raw("b")` produced invalid SQL.
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

`tests/support/test_string.py` checks that `to_embeddings` returns the faked vector and forwards provider, model and dimensions. `tests/masoniteorm/query/grammars/test_vector_grammar.py` checks the SQL and binding order of each vector query method, the order-by comma fix, the `TypeError` for text and the `ValueError` on non-Postgres grammars. `tests/masoniteorm/schema/test_vector_schema.py` checks `VECTOR(n)`, the HNSW index on create and alter, the extension SQL and the errors on other platforms. `tests/masoniteorm/models/test_caster.py` checks the JSON cast for generic annotations. `tests/masoniteorm/postgres/test_postgres_vector.py` runs against a live `pgvector/pgvector` database: it round-trips `list[float]` and checks similarity filtering, distance selection and ordering.

`uv run pytest --ignore=tests/masoniteorm/postgres --cov` passes with coverage at or above 80%.
