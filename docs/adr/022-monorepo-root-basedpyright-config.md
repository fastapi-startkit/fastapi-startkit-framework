# 022. Monorepo-root basedpyright configuration

- Date: 2026-10-19
- Status: Accepted

## Problem

Editors open the monorepo root, but the only basedpyright config is `[tool.basedpyright]` in `fastapi_startkit/pyproject.toml`, and CI runs `basedpyright` from `fastapi_startkit/`. From the root, basedpyright finds no config, so it:

- uses the repo root as the only execution root. The `fastapi_startkit/` project directory then resolves as a namespace package, so `fastapi_startkit.masoniteorm...` imports inside `src/` are flagged as `reportImplicitRelativeImport`, with a suggested path of `fastapi_startkit.src.fastapi_startkit...`.
- ignores `fastapi_startkit/.venv` and resolves third-party packages from whatever interpreter is on `PATH`, which gives `reportMissingImports`.
- falls back to basedpyright's `recommended` mode, Python 3.14, and every `.py` file in the tree.

Counts from `basedpyright` on `main`:

| Run from | Files | Errors | Warnings | `reportImplicitRelativeImport` | `reportMissingImports` |
|---|---|---|---|---|---|
| `fastapi_startkit/` | 338 | 1 | 0 | 0 | 1 |
| repo root | 791 | 1969 | 34838 | 260 | 770 |

The imports are correct absolute imports. The fault is in the configuration, not the code.

## Alternatives

- **Rewrite the flagged imports as relative imports.** Wrong: they're correct for the installed package, and the rewrite would touch hundreds of files.
- **Root `pyrightconfig.json`.** Rejected: pyright looks for `pyrightconfig.json` in every parent directory before it looks for any `pyproject.toml`, so the root file would also override the package config when run from `fastapi_startkit/`, which changes what CI checks.
- **Move the package config into `fastapi_startkit/pyrightconfig.json` too.** Works, but it moves the CI config and conflicts with in-flight changes to `[tool.basedpyright]`.
- **Root `pyproject.toml` with only `[tool.basedpyright]`.** (chosen) pyright stops at the nearest `pyproject.toml`, so `fastapi_startkit/` keeps using its own config.

## Decision

Add a root `pyproject.toml` that contains only `[tool.basedpyright]`:

- `venvPath = "fastapi_startkit"`, `venv = ".venv"`: the package venv, which has every framework extra installed.
- `executionEnvironments`: `fastapi_startkit/src` as its own root, `fastapi_startkit` (tests) with `extraPaths` set to `src`, and one root per `example/*` app with `extraPaths` set to `fastapi_startkit/src`, because the examples import their own `bootstrap`, `config` and `app` packages as top-level modules.
- `include`, `exclude`, `typeCheckingMode = "standard"` and `pythonVersion = "3.12"` match the package config, plus `example`.

## Implementation

- New `pyproject.toml` at the repo root. It has no `[project]` table, so it isn't a uv project. Run uv commands from the member directories, as before: root `uv sync` already failed for lack of a `pyproject.toml`, and bare `uv run` at the root now reports a missing `project` table.
- No source, import or package config changes.

## Validation

`basedpyright` after the change:

| Run from | Files | Errors | Warnings | `reportImplicitRelativeImport` | `reportMissingImports` |
|---|---|---|---|---|---|
| `fastapi_startkit/` | 338 | 1 | 0 | 0 | 1 |
| repo root | 468 | 98 | 0 | 0 | 22 |

- The package-dir run is unchanged. Its one error is `langchain.chat_models`, which isn't installed on Python 3.15 (ADR 014).
- The extra root errors are all in `example/`. They're real example issues, such as optional dependencies missing from the package venv (`langgraph`, `psycopg`, `taskiq`, `fastapi_startkit_auth`), a missing `databases.factories.TicketFactory`, and Optional/override typing. They're left for follow-ups.
- `basedpyright --verbose` from the root shows `fastapi_startkit/.venv/.../site-packages` and `fastapi_startkit/src` in the search paths.
- The full pytest suite passes.
