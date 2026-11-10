# 079. Fix flaky `detach_related` and browser short timeout

- Date: 2026-11-10
- Status: Accepted

## Problem

The Test workflow on `main` failed twice in a row with different, intermittent failures:

1. Run 42748451153 (Python 3.13): `tests/playwright/test_browser.py::TestPage::test_failed_assertions_explain_what_was_expected` raised `Page.goto: Timeout 300ms exceeded`. The `short_timeout` fixture sets `browser_session.timeout` to 300 ms, and the session applies that value through `context.set_default_timeout`, which also bounds navigation. A loaded runner took longer than 300 ms to load a local page.
2. Run 42752939965 (Python 3.15): `tests/masoniteorm/sqlite/relationships/test_belongs_to_many.py::test_detach_related_removes_pivot_record` failed with `1 != 0`. `BelongsToMany.detach_related` added `created_at` and `updated_at` equal to `pendulum.now()` to the `WHERE` clause of the pivot delete when `with_timestamps` is set. The delete only matched when attach and detach ran within the same second, so detaching a record attached earlier silently did nothing. This is a real bug, not just a flaky test.

## Alternatives

- Retry flaky tests in CI: hides the `detach_related` bug and keeps tests nondeterministic.
- Add a separate navigation timeout to `BrowserSession`: a new framework option for a test-only concern.
- Make `detach_related` delegate to `detach`: `detach` also drops global scopes, which changes behaviour beyond the bug.

## Decision

- `BelongsToMany.detach_related` filters the pivot delete by the local and foreign keys only, the same keys `detach` uses.
- The `short_timeout` test fixture uses 1000 ms, which keeps failing assertions fast while leaving navigation enough headroom on CI runners.

## Validation

- New regression test `test_detach_related_removes_pivot_record_attached_earlier` patches `pendulum.now` so attach and detach happen five seconds apart; it fails before the fix and passes after.
- `uv run pytest tests/` passes locally apart from MySQL tests that need a live server.
