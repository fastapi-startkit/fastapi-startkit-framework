# 019. Accurate code examples in shipped skill stubs

- Date: 2026-10-18
- Status: Accepted
- Issue: #182

## Problem

`fastapi_startkit/skills/stubs/.ai/fastapi-startkit/*/SKILL.md` are copied into downstream projects by the skills scaffolding, so agents and developers follow their snippets verbatim. Three snippets fail at runtime:

1. `fastapi/SKILL.md` calls `User.create(...)` without `await` in two controllers, and the action-pattern `handle()` is a sync `def`. The ORM methods are `async def`, so a coroutine reaches `JsonResource(...)`.
2. `inertia/SKILL.md` imports `InertiaResponse` from `fastapi_startkit.inertia`, which does not export it, so the import raises `ImportError`.
3. `inertia/SKILL.md` binds `ProjectStoreRequest(RequestModel)` as a bare parameter. FastAPI then treats it as a JSON body. The per-field `Form(...)` signature that `RequestModel` builds is only used when the model is a dependency, so an Inertia `useForm().post(...)` submission doesn't bind.

Nothing checked the stub snippets, so they drifted from the framework.

## Alternatives

- **Fix the snippets only.** Smallest change, but the same drift can happen again.
- **Re-export `InertiaResponse` from `fastapi_startkit.inertia`.** This makes the documented import valid, but it changes the public API to fit a doc. Per ADR 013, `__all__` is curated, and the framework should change only when that's needed.
- **Auto-wrap `RequestModel` parameters in `Depends` in the router.** This is a behaviour change to routing that affects every app. It's out of scope for a doc bug.
- **Fix the snippets and add a static test over every stub's Python blocks.** (chosen)

## Decision

Correct the snippets and guard them with a test that parses every ```` ```python ```` block in every shipped `SKILL.md` with `ast`. The test makes no framework changes.

## Implementation

- `fastapi/SKILL.md`: `await User.create(...)` everywhere, and `async def handle(...)` in the action pattern.
- `inertia/SKILL.md`: `from fastapi_startkit.inertia import Inertia` plus `from fastapi_startkit.inertia.inertia import InertiaResponse`; the store example uses `request: ProjectStoreRequest = Depends()`, which matches `example/inertia-pingcrm-app`, and the prose says a bare annotation is read as JSON.
- `tests/skills/test_stub_examples.py` runs three checks on every stub:
  - every `from fastapi_startkit... import name` resolves;
  - calls to the async ORM methods (`create`, `update`, `find`, `find_or_fail`, `all`, `get`, `first`) on a capitalised model name are awaited, and none are inside a sync `def`;
  - parameters annotated with a class the stub defines as a `RequestModel` subclass default to `Depends(...)`.

## Validation

- The new test fails on `main` for the three reported bugs and passes after the fix.
- Full suite with coverage, ruff and basedpyright are clean.
