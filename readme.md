# FastAPI Startkit

[![codecov](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-modules/branch/main/graph/badge.svg)](https://codecov.io/gh/fastapi-startkit/fastapi-startkit-modules)
[![PyPI version](https://img.shields.io/pypi/v/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-startkit.svg)](https://pypi.org/project/fastapi-startkit/)

A modular, provider-driven framework for building Python applications with FastAPI. Full documentation is available at [fastapi-startkit.github.io](https://fastapi-startkit.github.io).

## Setup

After cloning, activate the git hooks:

```sh
git config core.hooksPath .githooks
```

This enables the pre-commit hook that runs `ruff check --fix` on the core package before every commit.