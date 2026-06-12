---
name: fastapi-best-practices
description: "Apply this skill whenever writing, reviewing, or refactoring FastAPI Startkit code. Covers controllers, ORM models, migrations, providers, console commands, HTTP clients, validation, error handling, and architectural decisions. Use for code reviews and refactoring existing code to follow framework best practices."
license: MIT
metadata:
  author: fastapi-startkit
---

# FastAPI Startkit Best Practices

Best practices for FastAPI Startkit, prioritized by impact. Each rule teaches what to do and why. For exact API syntax, verify with the framework docs.

## Consistency First

Before applying any rule, check what the application already does. FastAPI Startkit offers multiple valid approaches — the best choice is the one the codebase already uses, even if another pattern would be theoretically better. Inconsistency is worse than a suboptimal pattern.

Check sibling files, related controllers, models, or tests for established patterns. If one exists, follow it. These rules are defaults for when no pattern exists yet, not overrides.

## Quick Reference

### 1. HTTP Client → `rules/http-client.md`

- Explicit `timeout` and `connect_timeout` on every request
- `retry()` with exponential backoff for external APIs
- Check response status or use `raise_for_status()`
- Use `asyncio.gather()` for concurrent independent requests
- Mock HTTP clients with `httpx` fakes and `respx` in tests

### 2. ORM Queries → `rules/orm-queries.md`

- All DB operations are `async` / `await`
- Eager load relationships to prevent N+1 queries
- Use `exists()` to check without fetching rows
- `chunk()` for large datasets to avoid memory issues
- Index columns used in `WHERE`, `ORDER BY`

### 3. Validation → `rules/validation.md`

- Use Pydantic models for all request bodies
- Declare `response_model` on every endpoint
- Never trust raw user input — always validate shapes and types
- Return structured error responses with RFC 7807 format

### 4. Error Handling → `rules/error-handling.md`

- Register custom exception handlers in your provider
- Use `HTTPException` for client errors, custom exceptions for domain errors
- Always log unexpected exceptions with context
- Never expose internal stack traces to clients

### 5. Providers & Container → `rules/providers.md`

- Bind services in `register()`, resolve dependencies in `boot()`
- Inject via the container — avoid `app().make()` in business logic
- Use facades for static-style access; add `.pyi` stubs for IDE support

### 6. Console Commands → `rules/console-commands.md`

- Extend `Command` from `fastapi_startkit.console`
- Use `option()` and `argument()` helpers for CLI args
- Register commands in your provider's `boot()` via `self.commands([...])`
- Keep `handle()` thin — delegate to services

### 7. Testing → `rules/testing.md`

- Use `pytest` with `asyncio_mode = "auto"`
- Reset the container singleton between tests
- Use `tmp_path` for filesystem isolation
- Mock external services — never hit real APIs in tests

## How to Apply

1. Identify the area of work and select relevant rule sections above
2. Check sibling files for existing patterns — follow those first
3. Verify API syntax with the framework docs for the installed version
