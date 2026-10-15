---
title: Explicit re-exports from package __init__ modules
date: 2026-10-14
---

## Why

The core package ships `py.typed`. basedpyright, like pyright, treats a name imported into a `py.typed` package's `__init__.py` as private unless it is re-exported explicitly. `from fastapi_startkit.environment import env` therefore reports `reportPrivateImportUsage` in consumer editors, even though `fastapi_startkit.environment` is the documented import path in the docs, example apps and the `application/` starter. The same failure applies to every other public name imported into a package `__init__.py` without an explicit export list.

## Alternatives

- **Tell users to import from the implementation module** (`fastapi_startkit.environment.environment`). Rejected: it contradicts the documented API and leaks internal layout to every consumer.
- **Disable `reportPrivateImportUsage` in the project config.** Rejected: it hides the signal for consumers who type-check this package, and does not fix the published typing surface.
- **Use `from .x import y as y` aliases.** Valid, but it is noisier than `__all__` and gives no single list of the public surface.
- **Declare `__all__` in each package `__init__.py`.** Chosen: pyright accepts names listed in `__all__` as re-exports, and the list documents the public surface in one place. This is the convention already used by `config`, `fastapi`, `logging`, `masoniteorm`, `redis` and others in this repo.

## Decision

Every package `__init__.py` under `fastapi_startkit/src/fastapi_startkit/` that imports public names and lacks an export list gets an `__all__` listing exactly those imported names. `environment/__init__.py` exports `env` and `value`. No import statement is changed, so runtime import order and behaviour are unchanged.

## Implementation

- Add `__all__` to the package `__init__.py` files that currently import names without declaring them, including `environment`, `configuration`, `container`, `carbon`, `exceptions`, `facades`, `loader`, `logging/*`, and `masoniteorm/*` subpackages.
- Leave modules with no imports, and modules that already declare `__all__`, unchanged.
- Star-import contents of these packages shrink to the declared names. Submodule attributes are no longer picked up by `from pkg import *`, which no documented usage relies on.

## Validation

- basedpyright on a scratch file importing `env` from `fastapi_startkit.environment`, before and after the change.
- basedpyright over `example/` and `application/` filtered for `reportPrivateImportUsage` on `fastapi_startkit` imports, before and after.
- `cd fastapi_startkit && uv run pytest tests/` with the Postgres suite ignored when no database is available.
- Import smoke test of every touched package to confirm no circular import is introduced.
