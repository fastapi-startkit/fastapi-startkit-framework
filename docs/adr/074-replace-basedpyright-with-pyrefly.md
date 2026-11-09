# 074. Replace basedpyright with Pyrefly

- Date: 2026-11-08
- Status: Accepted
- Supersedes: [020](020-mcp-modern-typing-syntax.md), [021](021-enable-deprecated-and-type-argument-checks.md)

## Problem

CI type-checks the package with basedpyright in `standard` mode. ADR 021 turned on `reportDeprecated` and `reportMissingTypeArgument` only as warnings, so `uv run basedpyright` never fails on them, and the rest of the strict rules stay off. Applications built on the framework, such as salut-ai, already check with Pyrefly. Two checkers disagree on the same code, and framework changes are not checked the way their callers are.

The configuration was also split. A root `pyproject.toml` held only `[tool.basedpyright]` for editors, covering the package and every example, while `fastapi_startkit/pyproject.toml` held the configuration CI ran.

## Alternatives

- **Keep basedpyright and move it to `recommended` or `all` mode.** Fails CI on hundreds of existing hits at once, and basedpyright has its own baseline format the applications do not share.
- **Run both checkers.** Twice the CI time and two sets of suppressions for the same code.
- **Pyrefly with the `default` preset.** 61 errors, but it leaves out the annotation completeness and override checks that ADRs 020 and 021 were working towards.
- **Pyrefly with the `all` preset.** 9,141 errors. It also turns on directive and debugging diagnostics such as `reveal-type` as errors.
- **Pyrefly with the `strict` preset and a baseline.** (chosen)

## Decision

Pyrefly replaces basedpyright. `[tool.pyrefly]` in `fastapi_startkit/pyproject.toml` uses `preset = "strict"` on `src/fastapi_startkit`, with the same excludes as before, and records the existing errors in `fastapi_startkit/pyrefly-baseline.json`. Baselined errors are ignored; any new error fails CI. Fixing code shrinks the baseline through `uv run pyrefly check --prune-baseline`; new errors are fixed, not added to it.

The root `pyproject.toml` is removed. Pyrefly finds the nearest configuration from each file, so package files use `fastapi_startkit/pyproject.toml` and examples use their own.

ADR 020's syntax changes stay. ADR 021's warning-only rules are replaced by the preset, where `implicit-any-type-argument` reports bare generics as an error.

## Implementation

- `fastapi_startkit/pyproject.toml`: `basedpyright` leaves the `dev` group, `pyrefly>=1.4.1` joins it, and `[tool.basedpyright]` becomes `[tool.pyrefly]`. `uv.lock` is relocked. `pyright` stays for the `pyrightconfig.typing-tests.json` check.
- `.github/workflows/lint.yml`: the `basedpyright` job becomes `pyrefly` and runs `uv run pyrefly check`.
- `fastapi_startkit/pyrefly-baseline.json`: 2,397 errors in 203 files, led by `implicit-any-parameter` (1,402), `missing-override-decorator` (478) and `implicit-any-type-argument` (390).
- `tests/core/test_structural_config.py`: the check that plain dataclasses satisfy the config protocols runs Pyrefly instead of basedpyright.

## Validation

- `uv run pyrefly check` from `fastapi_startkit/` reports 0 errors and exits 0. Without the baseline the strict preset reports 2,397.
- `uv run ruff check .` passes, and `tests/core/test_structural_config.py` passes with the Pyrefly check.
