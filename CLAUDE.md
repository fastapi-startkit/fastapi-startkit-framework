# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **monorepo** for the FastAPI Startkit ecosystem — a Laravel/Masonite-inspired framework for building Python applications with FastAPI. It contains four main components:

| Directory | Purpose | Published as |
|---|---|---|
| `fastapi_startkit/` | Core framework package | [`fastapi-startkit`](https://pypi.org/project/fastapi-startkit/) on PyPI |
| `fastapi_startkit.github.io.git/` | Documentation site | GitHub Pages (VitePress) |
| `example/` | Standalone example apps | Not published — reference only |
| `application/` | Starter application template | Not published — clone/scaffold target |

### `fastapi_startkit/` — Core Package

The PyPI package (`fastapi-startkit`, currently v0.13.6). Source lives under `src/fastapi_startkit/`. This is the foundational framework all other components depend on.

**Do not modify framework code unless explicitly necessary.** Changes to core abstractions (Container, Application, Model, Provider, Facades) can have broad breaking effects on downstream applications.

Optional extras are installed with pip/uv extras:

```
fastapi-startkit[fastapi]    # FastAPI + Starlette
fastapi-startkit[database]   # SQLAlchemy async ORM
fastapi-startkit[postgres]   # asyncpg driver
fastapi-startkit[sqlite]     # aiosqlite driver
fastapi-startkit[mysql]      # aiomysql driver
fastapi-startkit[vite]       # Jinja2 for Vite integration
```

### `fastapi_startkit.github.io.git/` — Documentation

VitePress site. Docs cover getting started, configuration, console, database, logging, FastAPI integration, frontend, and exception handling. Edit `.md` files under `docs/` and the home page at `index.md`.

### `example/` — Example Applications

Self-contained apps demonstrating specific features. Each subdirectory is an independent uv workspace member:

| App | What it shows |
|---|---|
| `config-app/` | Configuration system |
| `console-app/` | CLI / Cleo commands |
| `database-app/` | ORM, migrations, seeders |
| `fastapi-app/` | Minimal FastAPI setup |
| `inertia-pingcrm-app/` | Full Inertia.js + PingCRM clone |
| `onefile-app/` | Single-file application |
| `vite-app/` | Vite + Jinja2 frontend |

### `application/` — Starter Application

The template users clone when starting a new project. Contains the minimal scaffolding: `artisan` entrypoint, `bootstrap/`, `config/`, `providers/`, `routes/`, and `storage/`. It mirrors a typical project layout and is a uv workspace member of this monorepo.

## Commands

```bash
# Install all workspace dependencies
uv sync

# Build the core package
cd fastapi_startkit && uv build

# Run framework tests
uv run pytest fastapi_startkit/src/fastapi_startkit/tests/ -v

# Run a single test file
uv run pytest fastapi_startkit/src/fastapi_startkit/tests/configurations/test_config_merge.py -v

# Serve the docs locally
cd fastapi_startkit.github.io.git && npm run dev
```

Tests run with `asyncio_mode = "auto"` (configured in `pyproject.toml`), so all tests are async-capable by default.

## Test Coverage

Coverage is tracked with `pytest-cov`. All commands must be run from inside the `fastapi_startkit/` directory.

```bash
# Run tests with coverage — prints a summary table to the terminal
uv run pytest --cov

# Show which lines are not covered
uv run pytest --cov --cov-report=term-missing

# Generate an HTML report (opens in browser from htmlcov/index.html)
uv run pytest --cov --cov-report=html
open htmlcov/index.html

# Run both terminal and HTML reports at once
uv run pytest --cov --cov-report=term-missing --cov-report=html

# Skip tests that require a live Postgres connection (safe for local dev)
uv run pytest --ignore=tests/masoniteorm/postgres --cov --cov-report=term-missing --cov-report=html

# Run a specific test file with coverage
uv run pytest tests/core/test_container.py --cov --cov-report=term-missing
```

### Coverage configuration

Configured in `pyproject.toml` under `[tool.coverage.*]`:

| Setting | Value |
|---|---|
| Source tracked | `src/fastapi_startkit/` |
| Omitted | `*/tests/*`, `*/migrations/*`, `*/__init__.py`, `*.pyi` |
| Minimum threshold | `fail_under = 40` |
| HTML output dir | `htmlcov/` |

The test suite **fails** if total coverage drops below the `fail_under` threshold. Raise this value in `pyproject.toml` as coverage improves.

## Architecture (Core Package)

### Application Lifecycle

1. `Application(base_path)` initializes the service container and singleton
2. `.load_environment()` loads `.env` + `.env.{APP_ENV}` (auto-detects `.env.testing` under pytest)
3. `.configure_paths()` sets config/storage paths
4. `.register_providers()` → `.load_providers()` (two-phase boot)
5. `app.fastapi` is lazy-loaded; HTTP routes delegate to the FastAPI instance

### Service Container (`container/container.py`)

Central IoC container. Core API:
- `bind(key, value)` — register a binding
- `make(key)` — resolve a binding
- `resolve(obj)` — auto-wire a callable by inspecting its type-hinted parameters

Hooks (`on_bind`, `on_make`, `on_resolve`) allow intercepting container operations. `collect('Auth*')` returns all bindings matching a wildcard.

### Configuration (`configuration/`)

Define config as a dataclass with fields sourced from environment variables via `env()`:

```python
from dataclasses import dataclass, field
from fastapi_startkit.environment import env

@dataclass
class RedisConfig:
    host: str = field(default_factory=lambda: env('REDIS_HOST'))
    port: int = field(default_factory=lambda: env('REDIS_PORT'))
```

`app.load_environment()` applies a two-step merge: `.env` as base, then `.env.{APP_ENV}` on top.

Register in the container for dotted-key access:

```python
config = app.make('config')
config.set('redis', RedisConfig())

Config.get('redis.host')   # via facade
```

### Provider Pattern (`providers/`)

Providers are the standard way to register services. Each provider has two phases:
- `register()` — bind things into the container
- `boot()` — run after all providers are registered (safe to resolve dependencies here)

### FastAPI Routing (`fastapi/routers/router.py`)

`Router` wraps FastAPI's `APIRouter` and adds a `resource()` shortcut.

```python
from fastapi_startkit.fastapi import Router

router = Router()
router.get("/path", endpoint)
router.post("/path", endpoint)
router.put("/path", endpoint)
router.patch("/path", endpoint)
router.delete("/path", endpoint)
```

`router.resource(name, controller)` registers standard CRUD routes (index, create, store, show, edit, update, destroy). Use `only=`, `excepts=`, `names=`, `parameters=` to customise.

Group routes by access level using separate `Router` instances:

```python
# routes/web.py
from fastapi import Depends
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", auth_controller.create)
guest.post("/login", auth_controller.store)

auth = Router(dependencies=[Depends(auth_middleware)])
auth.get("/", dashboard_controller.index)
auth.resource("users", users_controller)
```

### ORM (`masoniteorm/`)

Async-first fork of Masonite ORM built on SQLAlchemy async:
- All DB operations are `async`/`await`
- `Model` auto-pluralizes table names via `inflection`
- `created_at`/`updated_at` managed as `pendulum` Carbon objects
- Relationships: `HasOne`, `HasMany`, `BelongsTo`, `BelongsToMany`, `HasOneThrough`
- `AsyncQueryBuilder` provides the chainable query interface

### Facades (`facades/`)

Static-like access to container-resolved services (`Config.get()`, `Auth.user()`, etc.). Each facade has a `.pyi` stub for IDE type support. Requires a booted Application singleton.

### Console (`commands/`, `masoniteorm/commands/`)

CLI built on [Cleo](https://github.com/python-poetry/cleo). Database commands (migrate, seed, make:model, etc.) live in `masoniteorm/commands/`. Run via `uv run artisan`.

## Key Dependencies

| Package | Purpose |
|---|---|
| `fastapi[standard]` | HTTP framework (lazily imported) |
| `sqlalchemy[asyncio]` | Async ORM backend |
| `pendulum` | Datetime/timezone (used as Carbon) |
| `cleo` | CLI commands |
| `dotty-dict` | Nested dict access via dotted keys |
| `inflection` | Table name pluralization |
| `asyncpg` / `aiomysql` / `aiosqlite` | DB drivers |
