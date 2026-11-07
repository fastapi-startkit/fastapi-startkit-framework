# 067. Async browser tests on one event loop

Date: 2026-11-07

## Problem

ADR 063 drove the browser with Playwright's sync API and ran the application under test in a uvicorn thread with its own event loop. The ORM, factories and seeders are async and their connections belong to that server loop, so a sync test could only reach the database through `self.query(coroutine)`, which shipped the coroutine to the server thread. `DatabaseTruncation` did the same behind a fixture. Tests read nothing like Pest:

```python
user = self.query(User.where("email", "ada@example.com").first())
```

The rest of the framework is async by default, so browser tests should be too: `await User.where(...).first()` and `await UserFactory.new().create(...)` on the same connection the application uses.

Making only the test `async` does not work with the sync driver. Sync Playwright blocks whatever loop calls it, so a test running on the server loop would block the server while the browser waits for it to answer.

## Alternatives

1. **Keep sync tests and `self.query`.** No churn, but every database touch needs the wrapper, and the API stays the odd one out in an async framework.
2. **Async tests on their own loop, sync Playwright moved to a worker thread, per-loop database connections.** The test and the application would use different connections, the ORM would need loop-keyed connection caches, and every raw Playwright call would need marshalling to the driver thread.
3. **Everything on one loop: the test, the application server, the browser driver and the database.** Playwright's async API, uvicorn served as a task on that loop, and the page chain made awaitable.

## Decision

Option 3. There is no sync path; browser tests are `async def`.

### One session loop

`BrowserTestCase` carries `pytest.mark.asyncio(loop_scope="session")`, so its tests and its fixtures run on pytest-asyncio's session loop. The live server, the Playwright driver, launched browsers and the application's database connections are created on that loop and live until the session ends. A session fixture from the plugin, `browser_session_lifetime`, closes pages and browsers, stops the driver and stops the server on that loop at the end of the session. The plugin registers it only when pytest-asyncio is installed, so the entry point stays harmless in projects without the extra; `fastapi-startkit[playwright]` now depends on `pytest-asyncio`.

### Live server as a task

`LiveServer.start()` and `stop()` are coroutines. The server binds a free port and runs `uvicorn.Server.serve` as a task on the running loop. uvicorn's signal capture is disabled for this embedded server, so Ctrl-C still interrupts pytest. `start()` fails with the same messages as before when the application stops before it started or does not start in time. `LiveServer.run()` and `BrowserTestCase.query()` are removed.

### Awaitable page chains

`visit(url)` still returns a `Page` without opening anything, and configuration (`on().mobile()`, `firefox()`, `with_locale()`…) stays synchronous. Actions and assertions are recorded when called and return the page, so the chain reads as before; awaiting the page opens it if needed, runs the recorded steps in order and returns the page:

```python
page = await visit("/login").fill("email", "ada@example.com").click("submit").assert_see("Dashboard")
await page.click("Log out").assert_url_is("/login")
```

- Readers are coroutines that run the pending steps first: `await page.text("h1")`, `await page.value("email")`, `await page.attribute(...)`, `await page.script(...)`, `await page.content()`.
- `page.playwright` is the opened async Playwright page; using it before the page has been awaited raises `RuntimeError`. `url` and `path` read the opened page.
- Callbacks given to `with_key_down` and `within_frame` add steps that run inside the callback's scope, before the steps that follow it. A callback may be an async function.
- A failing step stops the chain, drops the steps after it and raises the `AssertionError` from ADR 063/065.
- A chain that is never awaited would silently test nothing, so the end of each browser test fails with `"... was never awaited"` when a page still has recorded steps.

### Test setup

`BrowserTestCase` has an autouse session-loop fixture that, per test, selects `get_application()` for the session, starts (or restarts, for a different application) the live server, then awaits `asyncStartTestRun()` when the class defines one, before the test; afterwards it awaits `asyncStopTestRun()`, takes failure screenshots and pauses in `--debug`, checks for unawaited chains and closes the test's pages. These are the hooks `fastapi_startkit.testing.TestCase` already calls, so `DatabaseTruncation` works in both without knowing about the browser; its live-server fixture is removed. A sync test method on a `BrowserTestCase` fails with a message asking for `async def`.

The class mark covers the tests, not the user's own async fixtures: pytest-asyncio runs those on their own caching scope's loop, where the browser and the application's connections are unusable. A browser test's async fixtures are declared with `@pytest_asyncio.fixture(loop_scope="session")`, or the project sets `asyncio_default_fixture_loop_scope = "session"`, as the example app does.

The plugin's `pytest_runtest_makereport` only records the call-phase report on the item; the fixture reads it at teardown to attach screenshot paths to the failure. `--headed`, `--debug` selection of tests calling `.debug()`, and the ini options from ADR 063 are unchanged. The sync-driver bookkeeping (`needs_event_loop`, stopping the driver around async tests) is gone.

## Implementation

- `playwright/server.py`: async `LiveServer` serving on the running loop.
- `playwright/session.py`: async driver, browsers, contexts, failure screenshots, pauses and shutdown; `configure()` stays sync and records the application, which `serve()` (re)starts lazily.
- `playwright/base.py`, `interactions.py`, `assertions.py`, `page.py`: the recorded-step page on the async API. `assertions.py` takes the ADR 063 assertions; ADR 065's remaining assertions are built on it afterwards.
- `playwright/test_case.py`, `plugin.py`, `masoniteorm/testing/truncation.py` as above.
- The example app's browser tests become async, create users with `UserFactory` and query with the ORM directly.

## Validation

`tests/playwright/test_browser.py` runs as async browser tests: chains are lazy until awaited, steps run in order, readers flush pending steps, nested callbacks run in place, a failing step drops the rest, an unawaited chain fails the test, failure screenshots and debug pauses, devices and browsers, the live server's start, stop and failure messages, and `get_application()` switching servers. `tests/masoniteorm/testing/test_database_truncation.py` covers truncation through a `BrowserTestCase`. The example app's tests pass in Chromium and Firefox with database assertions made through the ORM and factories.
