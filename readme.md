# FastAPI Startkit

[![codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework/branch/main/graph/badge.svg)](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-framework)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)

A modular, provider-driven framework for building Python applications with FastAPI. Full documentation is available at [fastapi-startkit.github.io](https://fastapi-startkit.github.io).

## Python versions

Python 3.12, 3.13, 3.14 and 3.15 are supported. Python 3.16 is tested experimentally. The `fastapi-startkit[ai]` extra cannot be installed on Python 3.15 or newer yet, because its `langgraph` dependency requires `ormsgpack`, which does not support 3.15. Use Python 3.14 or older for the `ai` extra.

## Setup

After cloning, activate the git hooks:

```sh
git config core.hooksPath .githooks
```

This enables the pre-commit hook that runs `ruff check --fix` on the core package before every commit.