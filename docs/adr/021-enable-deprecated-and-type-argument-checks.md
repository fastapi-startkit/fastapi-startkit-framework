# 021. Enable basedpyright deprecation and missing type argument checks

- Date: 2026-10-18
- Status: Accepted

## Problem

`[tool.basedpyright]` uses `typeCheckingMode = "standard"`, which turns off `reportDeprecated` and `reportMissingTypeArgument`. Editors running basedpyright's default profile still show "This type is deprecated as of Python 3.10" and "Expected type arguments for generic class" warnings that CI never reports. `reportDeprecated` on its own also misses the `typing.Optional`/`List`/`Dict` aliases. It flags them only when `deprecateTypingAliases` is on, so with the rule enabled but without that flag it found 1 hit instead of 282.

Baseline with all three settings on: 282 `reportDeprecated` and 435 `reportMissingTypeArgument` hits across the package. That includes `mcp/` (30 and 32), which ADR 020 fixes separately.

## Alternatives

- **Switch to `recommended` or `all` mode.** Turns on many unrelated rules at once.
- **Enable the rules as `error` and fix everything in one PR.** About 90 files, too large to review. Changes are capped at 10 files per PR.
- **Enable the rules as `warning`, fix the files with the most hits, and follow up in further PRs.** (chosen)

## Decision

Set `deprecateTypingAliases = true`, `reportDeprecated = "warning"` and `reportMissingTypeArgument = "warning"` explicitly. The hits become visible in CI output without failing `uv run basedpyright`, which exits non-zero only on errors. Once every hit is fixed, both rules move to `"error"`.

Fix every hit in the seven files outside `mcp/` with the most hits: `fastapi/routers/router.py`, `vite/vite.py`, `inertia/inertia.py`, `ai/testing.py`, `exceptions/handler.py`, `ai/runner.py` and `process/process.py`.

## Implementation

- `Optional`/`Union`/`Type`/`List`/`Dict` become PEP 604 unions and builtin generics, and `Callable`/`Sequence`/`Iterable` are imported from `collections.abc` (`ruff --select UP006,UP007,UP035,UP045`).
- Type arguments come from usage where it shows them: `subprocess.Popen[str]` (every call uses `text=True`), `dict[str, str]` process environments, output callbacks `Callable[[str, str], Any]` and pool callbacks `Callable[[str, str, int], Any]`, `dict[str, int]` token and usage totals, `list[ToolCall]` for requested tool calls, `dict[str, list[str]]` preloaded asset attributes, and typed preload tuples.
- `dict[str, Any]` is used only for heterogeneous JSON-shaped data: Inertia props and pages, Vite manifests and tag attributes, agent state, stream events and cassettes. `Callable[..., Any]` is used for user-registered hooks whose arguments are deliberately loose, such as exception renderers, Vite attribute resolvers and test decorators.
- Annotation-only. `requires-python >= 3.12`, so the runtime-evaluated FastAPI router annotations are unaffected.

## Validation

- `uv run basedpyright`: the seven files report 0 hits. Package totals drop to 112 `reportDeprecated` and 262 `reportMissingTypeArgument` now that ADR 020 is merged, all warnings, with no new errors.
- `ruff check .` and `ruff format --check .` pass. The full suite passes with `--cov`.
