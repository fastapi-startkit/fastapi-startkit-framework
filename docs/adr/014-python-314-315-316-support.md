---
title: Python 3.14, 3.15 and 3.16 support
date: 2026-10-15
---

## Why

The core package declares `requires-python = ">=3.12,<4.0"` but only advertises and tests 3.12 and 3.13. On 2026-10-15 the release status is:

| Version | Status | Source |
|---|---|---|
| 3.14 | Final, bugfix (3.14.8) | python.org releases, PEP 745 |
| 3.15 | Final, 3.15.0 released 2026-10-09 | python.org releases, PEP 790 |
| 3.16 | Feature development, 3.16.0a1 only, final planned 2027-10 | python.org releases, PEP 826 |

Users on 3.14 and 3.15 get no signal that the package works there, and CI would not catch regressions. Three concrete problems showed up when running the suite on the new interpreters:

1. PEP 649/749 deferred annotations (3.14+) mean a class `__dict__` no longer holds `__annotations__`. `Caster.build_casts` falls back to `vars(klass).get("__annotations__", {})` when `get_type_hints` raises `NameError`, so on 3.14+ a model with one unresolvable forward reference silently lost every cast.
2. The locked versions of several compiled dependencies (pydantic-core, asyncpg, greenlet, uvloop, httptools, orjson, cffi, rignore, …) predate their cp315 wheels, and `rignore` 0.7.6 (via `fastapi[standard]`) cannot build from source on 3.15 because its PyO3 caps at 3.14.
3. `ormsgpack` (`langchain` → `langgraph` → `langgraph-checkpoint`) has no cp315 wheel and its PyO3 0.27 refuses 3.15. `PYO3_USE_ABI3_FORWARD_COMPATIBILITY` does not help because it uses non-limited CPython APIs.

## Alternatives

- **Pin `requires-python` below 3.15 until every dependency ships wheels.** Rejected: the core package and every runtime extra except `ai` already work on 3.15.
- **Gate the `ai` extra with environment markers on 3.15+.** Rejected: `pip install fastapi-startkit[ai]` would succeed but install a broken AI stack. A loud resolver failure is the more honest signal until `ormsgpack` ships 3.15 support.
- **Drop `langchain` from the dev group entirely.** Rejected: it removes AI test coverage on 3.12–3.14 for no gain.
- **Gate `langchain` in the dev group only, skip the tests that import it, and keep `langchain-core`.** Chosen: `langchain-core` installs on 3.15, so most AI tests keep running, and only the four test modules that patch `langchain.chat_models` skip.
- **Use `annotationlib.get_annotations(format=FORWARDREF)` behind a version check.** Rejected for now: `inspect.get_annotations` returns the same own-class annotations on 3.12 through 3.16 without a branch. Unresolvable unquoted forward references already fail earlier in `Model.__init_subclass__`.

## Decision

- Keep `requires-python = ">=3.12,<4.0"`, which already admits 3.14–3.16.
- Add Trove classifiers for 3.14 and 3.15 (final releases). Do not add 3.16 until it reaches final.
- CI `Pytest` becomes a matrix: 3.12, 3.13, 3.14, 3.15 are required; 3.16 runs with `continue-on-error`. Interpreters come from `uv python install`, because the `actions/setup-python` manifest has no 3.16 alpha. The 3.16 job builds PyO3 crates with `PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1`, skips installing `cffi` and `zstandard`, and runs pytest with `-p no:asyncio` so the synchronous tests still execute despite the upstream blockers. Example apps move to their own `Examples` job on 3.13, because `example/agents` needs the `ai` extra.
- `Caster.build_casts` reads own-class annotations through `inspect.get_annotations`.
- Refresh `uv.lock` for packages that gained cp315 wheels, using targeted `--upgrade-package` to avoid unrelated version churn.
- Mark `langchain` in the dev group with `python_version < '3.15'`; the four test modules that patch `langchain.chat_models` use `pytest.importorskip`.

## Implementation

- `fastapi_startkit/pyproject.toml`: classifiers `3.14`, `3.15`; dev dependency `langchain>=1.0.0; python_version < '3.15'`.
- `fastapi_startkit/uv.lock`: upgraded asyncpg, cffi, charset-normalizer, greenlet, httptools, markupsafe, orjson, pendulum, pydantic/pydantic-core, rapidfuzz, rignore, typing-extensions, typing-inspection, uvloop, watchfiles, xxhash.
- `src/fastapi_startkit/masoniteorm/models/caster.py`: `inspect.get_annotations(klass)` in the `NameError` fallback, with a regression test in `tests/masoniteorm/models/test_caster.py`.
- `tests/ai/test_agent.py`, `test_ai_fake.py`, `test_structured_output.py`, `test_agent_fake.py`: `pytest.importorskip("langchain.chat_models")`.
- `.github/workflows/test.yml`: `Pytest (Python X)` matrix, with `UV_PYTHON` pinned to the matrix version, `uv run --no-sync` for the test step, and per-entry `pyo3-forward-compat`, `sync-args` and `pytest-args` for 3.16. Coverage is uploaded from 3.13 only. Separate `Examples` job.
- `readme.md` and `fastapi_startkit/README.md`: supported versions, and a note that the `ai` extra cannot be installed on 3.15+.

## Upstream blockers

- `ormsgpack` 1.12.2 has no 3.15/3.16 support (PyO3 0.27). It blocks `fastapi-startkit[ai]` and `langchain` on 3.15+.
- `cffi` 2.1.1 does not compile against 3.16.0a1. Through `zstandard`/`langsmith` it blocks the dev environment on 3.16.
- `pytest-asyncio` 1.4.0 calls `asyncio.get_event_loop_policy`, which 3.16 removed. Every async test errors on 3.16.0a1. The framework itself does not use the event-loop policy API.
- Revisit 3.16 when it reaches beta, and lift the `langchain` marker once `ormsgpack` ships cp315 wheels.

## Validation

- `uv run --python 3.X pytest tests/ --ignore=tests/masoniteorm/postgres` on 3.12, 3.13, 3.14 and 3.15. The 3.15 run skips the four langchain-dependent modules and stays above the 80% coverage gate.
- 3.16.0a1 with the experimental job's settings: 2508 passed. The 212 failures and 55 errors are all async tests running without pytest-asyncio.
- The new caster test fails on 3.14 without the fix and passes on every version with it.
- `uv lock --check` with the older local uv still reads the refreshed lock.
