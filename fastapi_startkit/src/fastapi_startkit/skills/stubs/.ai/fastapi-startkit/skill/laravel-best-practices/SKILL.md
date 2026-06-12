---
name: laravel-best-practices
description: Architectural and code conventions for fastapi-startkit applications — provider pattern, container, resourceful controllers, ORM, routing, config, and async discipline.
---

# Laravel Best Practices for fastapi-startkit

This skill contains the canonical architecture rules for fastapi-startkit projects. The framework is heavily Laravel-inspired (provider pattern, IoC container, artisan commands, facades, ORM, resourceful routing), so conventions follow both Laravel idioms and Python/FastAPI specifics.

## Rules files

- [`rules/architecture.md`](rules/architecture.md) — 10 rules covering:
  1. Provider `register()` vs `boot()` separation
  2. Service container injection via `resolve()`, not service locator
  3. Single responsibility per `Provider`
  4. Resourceful controllers — `async def`, `ResourceCollection` return types
  5. ORM conventions — `await` discipline, relationship descriptors, minimal raw SQL
  6. Route organisation — guest/auth `Router` split, middleware at `Router` level
  7. Configuration via `@dataclass` + `env()`, no hardcoded values
  8. No business logic in routes or controllers — delegate to services
  9. Broadcasting — `BroadcastEvent` subclasses, `@channel` auth callbacks, no facades
  10. Async discipline — no blocking I/O in async context

## When to use

Apply these rules when:
- Starting a new fastapi-startkit application
- Reviewing a pull request for architecture compliance
- Deciding where to put new code (provider vs service vs controller vs model)
- Debugging async issues or unexpected blocking behaviour
