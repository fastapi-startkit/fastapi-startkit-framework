# FastAPI Startkit

[![codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework/graph/badge.svg)](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)

A modular, provider-driven framework for building Python applications with FastAPI. It bundles a
service container, configuration system, facades, and a Cleo-powered console into a single cohesive
foundation.

## Installation

Create a new application with the installer. It requires [uv](https://docs.astral.sh/uv/):

```bash
uvx fastapi-startkit init my-app
```

The installer asks which services, database, and frontend to set up, generates the project, and runs
`uv sync`. Then start the server:

```bash
cd my-app
uv run python artisan serve
```

Pass `.` to create the application in the current empty directory, or skip the prompts with options:

```bash
uvx fastapi-startkit init . --no-interaction
uvx fastapi-startkit init my-app --app=web --frontend=react
```

| Option | Values |
|---|---|
| `--app` | `web` (default), `worker`, or `both` |
| `--database` | `none`, `sqlite` (default), `postgres`, or `mysql` |
| `--frontend` | `none` (default), `react`, or `vue` |
| `--dry-run` | Show the plan without creating files |
| `--no-deps` | Generate files without installing Python dependencies |
| `-n`, `--no-interaction` | Use the defaults and option values without prompting |

Run `uvx fastapi-startkit init --help` for the full reference.

### Adding to an existing project

```bash
uv add fastapi-startkit
```

Optional extras enable additional capabilities:

```bash
fastapi-startkit[fastapi]    # FastAPI + Starlette
fastapi-startkit[vite]       # Jinja2 for Vite integration
fastapi-startkit[ai]         # LangChain agents
```

### Python versions

Python 3.12, 3.13, 3.14 and 3.15 are supported.

> [!NOTE]
> The `ai` extra cannot be installed on Python 3.15 or newer yet. It depends on `langgraph`, which
> requires `ormsgpack`, and `ormsgpack` does not support Python 3.15 yet. Use Python 3.14 or older for the
> `ai` extra. Every other extra works on 3.15.

## Features

- **Service container** — IoC container with `bind`/`make`/`resolve` auto-wiring and lifecycle hooks.
- **Configuration** — dataclass-based config sourced from the environment with dotted-key access.
- **Providers** — two-phase (`register` / `boot`) service registration.
- **Routing** — a `Router` wrapper around FastAPI's `APIRouter` with a `resource()` CRUD shortcut.
- **Facades** — static-like access to container-resolved services (`Config`, `Auth`, ...).
- **Console** — Cleo-based CLI (`artisan`) for serving the application and code generation.

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

Released under the [MIT License](https://github.com/fastapi-startkit/fastapi-startkit-framework/blob/main/LICENSE).
