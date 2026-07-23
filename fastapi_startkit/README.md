# FastAPI Startkit

[![codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework/graph/badge.svg)](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)

A modular, provider-driven framework for building Python applications with FastAPI. It bundles a
service container, configuration system, an async-first ORM, facades, and a Cleo-powered console into
a single cohesive foundation.

## Installation

```bash
pip install fastapi-startkit
```

Optional extras enable additional capabilities:

```bash
fastapi-startkit[fastapi]    # FastAPI + Starlette
fastapi-startkit[database]   # SQLAlchemy async ORM
fastapi-startkit[vite]       # Jinja2 for Vite integration
```

## Features

- **Service container** — IoC container with `bind`/`make`/`resolve` auto-wiring and lifecycle hooks.
- **Configuration** — dataclass-based config sourced from the environment with dotted-key access.
- **Providers** — two-phase (`register` / `boot`) service registration.
- **Routing** — a `Router` wrapper around FastAPI's `APIRouter` with a `resource()` CRUD shortcut.
- **ORM** — async-first Masonite ORM fork on SQLAlchemy async, with relationships and migrations.
- **Facades** — static-like access to container-resolved services (`Config`, `Auth`, ...).
- **Console** — Cleo-based CLI (`artisan`) for migrations, seeders, and code generation.

## Documentation

Full documentation is available at
[fastapi-startkit.github.io](https://fastapi-startkit.github.io).

## Development

```bash
# Install dependencies
uv sync --group dev --extra database --extra sqlite --extra fastapi --extra vite --extra postgres

# Run the test suite
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest --cov --cov-report=term-missing
```

Coverage is collected in CI and reported to
[Codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework).

## License

See the repository root for license details.
