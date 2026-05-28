# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start full dev server (Vite HMR + FastAPI backend together)
npm run dev

# Backend only
uv run python artisan serve

# Frontend only
npx vite dev

# Build frontend assets
npm run build

# Run tests
uv run pytest

# Run a single test file
uv run pytest tests/path/to/test_file.py -v
```

Python dependencies are managed with `uv`. After adding a new package to `pyproject.toml`, run `uv sync` from this directory.

## Architecture

This app is a FastAPI Startkit example demonstrating an LLM chat interface with Inertia.js + React on the frontend. It is a **uv workspace member** of the parent monorepo; `fastapi-startkit` is installed as an editable path dependency from `../../fastapi_startkit`.

### Request lifecycle

```
Browser → Inertia.js → FastAPI → Router → Controller → Agent → LangChain provider → LLM
```

- `routes/web.py` — defines all HTTP routes using `Router` (a thin wrapper over FastAPI's `APIRouter`).
- `app/controllers/` — handle HTTP requests; `chat_controller.store` returns a `StreamingResponse` backed by `agent.stream()`.
- `app/agents/` — subclasses of `Agent` from `packages/agent.py`.
- `app/requests/` — Pydantic models for request body validation.

### Application boot sequence

`bootstrap/application.py` instantiates `Application` with an ordered list of service providers:

```
LogProvider → AIProvider → FastAPIProvider → ViteProvider → InertiaProvider
```

Each provider has a `register()` phase (bind into container) and a `boot()` phase (safe to resolve dependencies). `FastAPIProvider.boot()` is where routes are mounted and Inertia is configured.

### Agent framework (`packages/agent.py`)

The core of the app. Agents are declared with class decorators and override lifecycle methods:

```python
@provider("anthropic")          # "anthropic" | "openai" | "google"
@model("claude-sonnet-4-6")
@max_tokens(2048)
class MyAgent(Agent):
    def messages(self):         # system prompt + few-shot history
        return [{"role": "system", "content": "..."}]

    def tools(self):            # list of callables — auto-wrapped as LangChain StructuredTools
        return [my_tool_fn]

    def schema(self):           # optional Pydantic model for structured output
        return MyOutputModel

    def before(self, message):  # pre-processing hook
        return message

    def after(self, response):  # post-processing hook
        return response

    def provider_options(self): # provider-specific kwargs (e.g. extended thinking)
        return {"anthropic": {"thinking": {"type": "enabled", "budget_tokens": 1024}}}
```

- `agent.prompt(message)` — full agentic loop (supports tool calls, up to `_max_steps` iterations).
- `agent.stream(message)` — token-by-token streaming iterator; **tool calls are not supported** during streaming.
- `agent.fake(patterns)` / `agent.assert_prompted()` — test helpers for offline replay and call assertions.

Provider credentials are resolved from the framework's `Config` facade first, falling back to direct environment variables. API keys live in `.env` and are loaded by `AIConfig` in `packages/config.py` via `AIProvider`.

### Memory system (`memory.py` / `memory.md`)

A production-grade memory system is being built for this app. The architecture (documented in `memory.md`) has seven layers:

| Layer | Responsibility |
|---|---|
| **Memory Router** | Classify input and route to the right store |
| **Semantic Memory** | Facts, preferences, long-term knowledge (PostgreSQL + pgvector) |
| **Episodic Memory** | Append-only event/conversation log |
| **Task Memory** | Goals, todos, agent progress |
| **Retrieval Layer** | Hybrid search with similarity + recency + importance scoring |
| **Working Memory** | Active context injected into the LLM prompt |
| **Reflection Engine** | Summarises episodes into semantic memories |

The fluent API is:

```python
memory.capture(...)
memory.search(...)
memory.semantic.add(...)
memory.tasks.create(...)
memory.reflect()
```

### Frontend

React + Inertia.js rendered inside `templates/index.html` (Jinja2). Pages live in `resources/js/Pages/` and are resolved by the Inertia adapter. The active page for the chat is `resources/js/Pages/Chat/Index.tsx`.

Vite serves assets in dev (HMR) and writes hashed bundles to `public/` on build. The `fastapi-vite-plugin` handles the manifest integration between Vite and the Python backend. Path alias `@/` maps to `resources/js/`.

### AI provider config

`packages/config.py` defines `AIConfig`, `AnthropicConfig`, `OpenAIConfig`, and `GoogleConfig` as dataclasses using `env()` for environment variable resolution. `AIProvider` registers `AIConfig` into the container under the `"ai"` key. Inside agents, `_provider_config()` resolves credentials via `Config.get("ai").providers[provider_name]`.

Switch the active provider by setting `AI_PROVIDER=anthropic|openai|google` in `.env` and updating the `@provider` / `@model` decorators on the agent class.
