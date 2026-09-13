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

### Typed ORM fields

Declare fields with `Field[T]()` to specify their Python type. A concrete default
can supply the type, as in `Field(default=False)`:

```python
from pydantic import BaseModel

from fastapi_startkit.masoniteorm import Field, Model


class Address(BaseModel):
    city: str


class User(Model):
    id = Field[int]()
    name = Field[str]()
    email = Field[str]()
    is_admin = Field(default=False)
    address = Field[Address]()
```

Instance attributes expose the declared types, and the ORM uses those types for
runtime casting. Nested Pydantic models such as `Address` are serialized to JSON
and reconstructed when read. Descriptor fields participate in `fill()` and
`update()` just like annotated fields. Existing annotated declarations remain
supported, and the base `Model` registers `Field` with `dataclass_transform` for
static analysis. This decorator does not generate a runtime constructor or
validate that every required field was supplied.

`ModelField` remains defined and publicly importable for compatibility:

```python
from fastapi_startkit.masoniteorm import ModelField


class LegacyUser(Model):
    address: Address = ModelField()
```

Constructing `ModelField()` emits a `DeprecationWarning`. It is scheduled for
removal in **2.x**; migrate `address: Address = ModelField()` to
`address = Field[Address]()`.

## Development

```bash
# Install dependencies
uv sync --group dev --extra database --extra sqlite --extra fastapi --extra vite --extra postgres

# Run the test suite
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest --cov --cov-report=term-missing

# Check lint, formatting, and types
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
```

Coverage is collected in CI and reported to
[Codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework).

Ruff and basedpyright failures fail their CI jobs. Basedpyright checks
`src/fastapi_startkit` in standard mode, without a baseline; existing type errors
must be addressed for that job to pass. Release notes are maintained in
[GitHub Releases](https://github.com/fastapi-startkit/fastapi-startkit-framework/releases).

## License

See the repository root for license details.
