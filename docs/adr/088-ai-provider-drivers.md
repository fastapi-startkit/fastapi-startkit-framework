# 088. AI providers resolve through their driver

Date: 2026-11-17

## Problem

Every provider config under `ai.providers` has a `driver` field, but nothing read it. `Lab.get_provider(name)` called `Lab(name)`, a closed `StrEnum` of `google`, `openai`, `anthropic`, `elevenlabs` and `bedrock`, so the provider name was also its identity. A provider called `local` raised a bare `ValueError` from the enum, and there was no way to point an agent at Ollama, LM Studio, vLLM or any other OpenAI-compatible server. `Ai.build` also passed only `api_key` and the Bedrock client options to `init_chat_model`, so `OPENAI_BASE_URL` was honoured by images and audio but not by chat.

## Alternatives

1. Keep name-based resolution and add `ollama` and `local` enum members. It stays closed: a second OpenAI-compatible server would need another enum member.
2. A registry where applications register driver classes. Flexible, but it adds a new extension point before anyone needs one and duplicates what `init_chat_model` already does.
3. Separate the configured provider (its name) from its driver (a `Lab` member). The name selects the config entry, the config's `driver` selects the LangChain integration.

## Decision

Option 3.

- `LabConfig(name, driver)` in `ai/lab.py` is built by `LabConfig.resolve(provider=None, model_type=TEXT)`: the name falls back to `ai.default*`, the driver is `ai.providers.{name}.driver`, falling back to the name so built-in providers keep working without a config entry. A driver outside `Lab` raises `ValueError("AI provider 'x' uses unknown driver 'y'. Use one of: ...")`.
- Settings (`key`, `url`, `models.*`, client options) are read by provider name; the LangChain provider key and option mappings come from the driver.
- `Lab` gains `openai-compatible` (LangChain `openai`) and `ollama` (LangChain `ollama`). Its instance methods delegate to `LabConfig(self.value, self)`, `Lab.get_provider` returns the resolved driver and `Lab.get_model_url` resolves by name, so existing callers and tests are unchanged.
- `Ai.build`, `Embeddings` and `Classification` resolve a `LabConfig`. Results report the provider name. Classification uses the Decisions API when the driver is `google`.
- `url` is passed as `base_url` for `openai-compatible` and `ollama` (chat and embeddings) and for `openai` chat. OpenAI embeddings keep their current arguments.
- `openai-compatible` sends `key` as `api_key`, or the placeholder `not-needed` when empty, because `ChatOpenAI` refuses to start without a key and local servers ignore it. Its embeddings use `OpenAIEmbeddings` with `check_embedding_ctx_length=False`, since non-OpenAI servers expect text, not tiktoken ids.
- `ollama` uses the native `ChatOllama`/`OllamaEmbeddings` from `langchain-ollama`, not an alias of `openai-compatible` at `{url}/v1`. The native client supports Ollama's tool calling, structured output and model options, and does not need a key. Users who prefer the OpenAI endpoint can configure `openai-compatible` with `url=http://localhost:11434/v1`. Ollama embeddings reject `dimensions()` with a clear error.
- New `OpenAICompatibleConfig` (driver `openai-compatible`, empty `key`/`url`/`models`) and `OllamaConfig` (driver `ollama`, `OLLAMA_BASE_URL` default `http://localhost:11434`, models `llama3.1` and `nomic-embed-text`), exported from `fastapi_startkit.ai`. `AIConfig` registers `ollama` by default. A new `ollama` extra is `fastapi-startkit[ai]` plus `langchain-ollama`.
- Image and audio still select factories by name (`openai`, `google`, `stability`, `elevenlabs`) and already raise a clear error for any other name. They are unchanged.

## Validation

- `tests/ai/test_provider_drivers.py`: custom names resolve through `driver`, built-in names still resolve, a custom default provider, unknown and missing drivers raise errors naming provider and driver, `init_chat_model` (mocked) receives `base_url`/`api_key` for `openai-compatible`, the keyless placeholder, `base_url` without `api_key` for `ollama`, `base_url` for `openai` chat, embeddings options for both drivers, and classification through a custom provider.
- Existing AI tests pass unchanged; full suite with `uv run pytest --ignore=tests/masoniteorm/postgres --cov`.
- With `langchain-openai` and `langchain-ollama` installed, building agents for a custom `openai-compatible` provider and for `ollama` returns `ChatOpenAI` and `ChatOllama` with the configured base URLs.
