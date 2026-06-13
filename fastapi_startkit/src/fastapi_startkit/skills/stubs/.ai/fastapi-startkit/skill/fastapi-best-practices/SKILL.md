---
name: fastapi-best-practices
description: Apply when writing or reviewing FastAPI Startkit code — routing, ORM, providers, commands, validation, and testing.
---

## Routing

- Use `Router` from `fastapi_startkit.fastapi`, not FastAPI's `APIRouter` directly.
- Use `router.resource(name, controller)` for CRUD; scope with `only=` or `excepts=`.
- Group routes by access level in separate `Router` instances (`guest`, `auth`).

## ORM

- All DB operations are `async`/`await` — never call ORM methods synchronously.
- Eager-load relationships to prevent N+1 queries.
- Use `exists()` to check presence without fetching rows.
- `chunk()` for large result sets.

## Providers

- Bind services in `register()`. Resolve dependencies only in `boot()`.
- Never call `app().make()` in business logic — inject via the container.

## Console commands

- Extend `Command` from `fastapi_startkit.console`.
- Register in provider `boot()` via `self.commands([...])`.
- Keep `handle()` thin — delegate to services.

## Validation & errors

- Pydantic models for all request bodies; declare `response_model` on every endpoint.
- Register custom exception handlers in a provider, not inline in routes.
- Never expose stack traces to clients.

## Testing

- `asyncio_mode = "auto"` in `pyproject.toml` — all tests are async-capable.
- Reset the container singleton between tests (`Container._instance = original`).
- Use `tmp_path` for filesystem isolation; never hit real external APIs.
