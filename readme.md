# FastAPI Startkit

[![codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework/branch/main/graph/badge.svg)](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)

A modular, provider-driven framework for building Python applications with FastAPI. Full documentation is available at [fastapi-startkit.github.io](https://fastapi-startkit.github.io).

## Create an application

After the installer is published, start with uv installed:

```sh
uvx fastapi-startkit init example-project
```

The wizard asks about the database and frontend. To generate a project without prompts:

```sh
uvx fastapi-startkit init example-project --database sqlite --frontend react --no-interaction
```

Use `--dry-run` to preview files or `--no-deps` to install Python dependencies later with `uv sync`. React and Vue templates require Node.js 22.12+; run `npm install` and `npm run dev` in a separate terminal. Queue workers and the hosted shell bootstrap are planned separately.

For local development before release, build the package and run `uvx --from /path/to/built.whl fastapi-startkit init example-project`.

## Python versions

Python 3.12, 3.13, 3.14 and 3.15 are supported. The `fastapi-startkit[ai]` extra cannot be installed on Python 3.15 or newer yet, because its `langgraph` dependency requires `ormsgpack`, which does not support 3.15. Use Python 3.14 or older for the `ai` extra.

## Setup

After cloning, activate the git hooks:

```sh
git config core.hooksPath .githooks
```

This enables the pre-commit hook that runs `ruff check --fix` on the core package before every commit.