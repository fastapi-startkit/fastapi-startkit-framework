# 020. Modern typing syntax in the MCP package

- Date: 2026-10-18
- Status: Accepted

## Problem

basedpyright reports two kinds of warning in `fastapi_startkit/src/fastapi_startkit/mcp`:

- `reportDeprecated` (30 hits): `typing.Optional`, `typing.Union` and `typing.Type`, deprecated since Python 3.9/3.10 in favour of `X | None`, `A | B` and `type[X]`.
- `reportMissingTypeArgument` (32 hits): bare `dict` and `list[dict]` annotations on JSON-RPC payloads, tool arguments and serialised `to_json()` output.

The package requires Python `>=3.12`, so the PEP 604 union syntax and builtin generics are valid at runtime, including in the Pydantic `JsonRpcRequest` model.

## Alternatives

- **Silence the rules in `[tool.basedpyright]`.** Hides the warnings but leaves the deprecated syntax.
- **Introduce `TypedDict`s for every MCP payload.** Most precise, but it's a larger API change than the user asked for, and tool/prompt `arguments` are user-defined, so they can't be typed by the framework.
- **Migrate to modern syntax and parameterise every bare generic.** (chosen)

## Decision

Replace `Optional[X]` with `X | None`, `Union[A, B]` with `A | B` and `Type[X]` with `type[X]`, and drop the `typing` imports that become unused. Every bare `dict` becomes `dict[str, Any]`, because all of them hold MCP/JSON-RPC wire data with string keys and heterogeneous values (strings, booleans, nested objects, lists). The core framework outside `mcp/` has the same warnings, but it isn't changed here.

## Implementation

- `ruff check --select UP006,UP007,UP035,UP045 --fixable ALL --fix` for the deprecated aliases, then a review by hand.
- Bare `dict` annotations in `argument.py`, `prompt.py`, `protocol.py`, `resource.py`, `response.py` and `tool.py` are now `dict[str, Any]`, with `Any` imported where needed.
- Annotation-only change. No runtime behaviour changes.

## Validation

- basedpyright with `reportDeprecated` and `reportMissingTypeArgument` enabled reports 0 of each on `mcp/` (was 30 and 32).
- `pytest tests/mcp -W error::DeprecationWarning` and the full suite with `--cov` pass.
