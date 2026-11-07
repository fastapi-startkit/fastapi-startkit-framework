# 063. Fluent browser testing with Playwright

Date: 2026-11-07

Superseded in part by ADR 067: tests are async, the page chain is awaited on Playwright's async API, and `self.query` is removed.

## Problem

Apps built on the framework, Inertia apps in particular, have no way to test what a user sees in a real browser. `HttpTestCase` sends requests through `ASGITransport`, so it never runs the frontend, follows a client-side Inertia visit, or fills a form. Writing raw Playwright against a live server means starting uvicorn by hand, managing browsers, contexts and base URLs, and writing CSS selectors for every button. We want tests that read like a user's script:

```python
from fastapi_startkit.playwright import BrowserTestCase, visit


class RegistrationTest(BrowserTestCase):
    def get_application(self):
        from bootstrap.application import app

        return app

    def test_user_can_sign_in(self) -> None:
        page = visit("/register").on().mobile().firefox()

        (
            page.click("Sign In")
            .assert_url_is("/login")
            .assert_see("Sign in to your account")
            .fill("email", "tmgbedu@gmail.com")
            .fill("password", "password")
            .click("submit")
            .assert_see("dashboard")
        )
```

## Alternatives

1. **Depend on `pytest-playwright`.** It gives `page` fixtures but no live server, no fluent chain and no text-based element lookup, and its `--browser`/`--headed` options and fixtures would shape our API. Tests would still be raw Playwright.
2. **Async API (`await visit(...)`).** Matches the async-first framework, but every chained call needs its own `await`, which breaks the fluent chain the request asks for.
3. **Serve the app in a subprocess.** Isolates event loops, but loses in-process access to the app for future helpers (an authenticated-user assertion, factories) and needs an import string and environment plumbing for every app.
4. **Sync fluent wrapper over Playwright's sync API, with the app served by uvicorn in a background thread of the test process, and a pytest plugin wiring it up.**

## Decision

Option 4, shipped as `fastapi_startkit.playwright` behind a `playwright` extra (`fastapi-startkit[playwright]`, which adds `playwright` on top of the `fastapi` extra).

- `visit(path)` returns a lazy `Page`. Nothing starts until the first action or assertion, so device and browser can be chosen fluently first: `.on().mobile()`, `.on().tablet()`, `.on().desktop()`, `.on().device("Pixel 7")`, and `.chromium()`, `.firefox()`, `.webkit()`. Configuring an opened page raises `RuntimeError`.
- Actions return the page: `click`, `fill`, `check`, `uncheck`, `select`, `navigate`, `screenshot`. Assertions return the page too: `assert_see`, `assert_dont_see`, `assert_url_is`, `assert_path_is`, `assert_title`, `assert_value`. The underlying Playwright page is available as `page.playwright` for anything else.
- `screenshot(full_page=False, filename=None)` saves a PNG into `browser_screenshot_dir`, like Pest's `screenshot()`: the visible viewport by default, the whole scrollable page with `full_page=True`. The file is named after the running test (its node id, slugified) unless `filename` is given; `.png` is added when missing. Taking another unnamed screenshot in the same test overwrites the file.
- Elements are found by what a user sees. `click(target)` matches a button or link whose accessible name contains `target`, an element with that `id` or `name`, a `button`/`input` with that `type` (so `click("submit")` presses the submit button), or a selector when `target` starts with `#`, `.`, `[`, `//`, `css=`, `xpath=` or `text=`. `fill`, `check`, `select` and `assert_value` match a form control by label, `name`, `id` or placeholder, or by such a selector. Candidates are combined with `Locator.or_()` and the first match in document order wins, so Playwright's auto-waiting still applies. Values are placed in quoted attribute selectors, so any text is a valid target.
- Assertions go through Playwright's `expect`, so they wait for Inertia's client-side visits. `assert_see` is case-sensitive, like Dusk. `assert_url_is("/login")` compares against the live server's URL and ignores the query string and fragment; a full URL is compared as given. Failures raise `AssertionError` naming the target and the current path. A missing element raises `AssertionError` instead of Playwright's `TimeoutError`.
- `BrowserSession` holds the configuration, the live server, the Playwright driver, one launched browser per engine, and the pages opened by the current test. Each page gets its own browser context with `base_url` set to the server and the chosen device descriptor. Firefox does not support `is_mobile`, so the flag is dropped for Firefox and the viewport, user agent and touch support are kept.
- Browser test classes extend `BrowserTestCase` and return the application from `get_application()`, as `TestCase` and `HttpTestCase` do. An app usually puts this in one base class under `tests/` that its browser tests extend. Before a test's fixtures are set up, the plugin calls `get_application()` and hands the result to the session; returning the same object keeps the running server, returning a different one restarts it. There is no ini option or default import path for the app, so a page opened with no application configured raises `RuntimeError` pointing at `BrowserTestCase`.
- `BrowserTestCase.query(coroutine)` awaits a coroutine on the live server's loop and returns its result, so a sync browser test can check what the app wrote with the ORM, as `docs/testing/database.md` does in async tests: `self.query(User.where("email", email).first())`. The app's connections are bound to that loop, so awaiting there avoids a second set of connections.
- `LiveServer` takes `.fastapi` from an `Application` (anything else is served as an ASGI app; an `module:attribute` string is imported), binds a socket on `127.0.0.1` port 0 and runs `uvicorn.Server` on it in a daemon thread. It waits for `started`, and raises if the thread dies first. The app module is imported in the test process, so under pytest it boots with `APP_ENV=testing`.
- The pytest plugin is registered through the `pytest11` entry point and imports nothing from Playwright until a page opens, so installs without the extra are unaffected. It adds ini options `browser_default` (`chromium`), `browser_timeout` (milliseconds, default 5000) and `browser_screenshot_dir` (`tests/browser/screenshots`), and a `--headed` flag that shows the browsers (reused when `pytest-playwright` already defines it). Debugging rides on pytest's built-in `--debug`: when it is passed the browsers run headed too, and after a failed test call each open page is paused in the Playwright inspector so the failing state can be inspected before teardown closes it; resuming in the inspector continues the run. pytest owns `--debug`, so a plugin cannot register it, and passing it also makes pytest write its own trace to `pytestdebug.log`. On a failed test call the plugin saves a screenshot of every open page, named after the test node id, before pausing. It closes the test's pages at teardown and shuts the browsers and server down at session end.
- `page.debug()` debugs a single test, like Pest's `->debug()`: it limits the run to the tests that call it, shows the browser and pauses there in the Playwright inspector, then returns the page so the chain continues after resuming. The limit is applied at collection: the plugin parses each collected test function's source with `ast` and, when any contains a `.debug()` call with no arguments, keeps only those tests (the others are reported as deselected) and runs the browsers headed. Calls with arguments, such as `logger.debug("x")`, do not count, and tests whose source cannot be read are kept out of the check. Detection is by name, so an unrelated zero-argument `.debug()` call in a test also selects it.
- Browser tests are plain sync methods. Playwright's sync API cannot run inside a running event loop, so `async def` browser tests are not supported.
- While it runs, Playwright's sync driver registers its own loop as the main thread's running loop, so pytest-asyncio and `IsolatedAsyncioTestCase` fail with "cannot be called from a running event loop". The plugin therefore stops the driver (browsers included, the server stays up) at teardown when the next test needs a loop, and at the last test. A test needs a loop if its function is a coroutine, its class subclasses `IsolatedAsyncioTestCase`, or any of its fixtures is async. Consecutive sync browser tests share one driver and one browser per engine.
- Coverage cannot trace code run under Playwright's greenlets on the pure-Python tracer (Python 3.15), and the plugin module is imported before pytest-cov starts, so the module's measured coverage understates what the tests exercise. The total stays above the threshold.

`assert_authenticated()` is left out: the framework has no auth layer to ask yet.

## Example application

`example/browser-testing` gains register, login and dashboard pages (Inertia + Vue), a `users` migration, a `User` model with salted PBKDF2 password hashes (replaced by `fastapi-startkit-auth` in ADR 066), a session middleware, a seeder creating the demo account, and a committed `.env.testing` pointing at `databases/testing.sqlite`. The frontend is built (`npm run build`) or served by `npm run dev` before the tests run; the tests do not build it. The database is reset by `DatabaseTruncation` (ADR 064). `tests/browser/test_case.py` defines the app's `TestCase(BrowserTestCase)` returning `bootstrap.application.app`, which the browser tests extend. The example sets `python_classes = ["Test*", "*Test"]` so `RegistrationTest` is collected, and uses the local framework through `tool.uv.sources`.

## Validation

- `fastapi_startkit/tests/playwright/` serves a small FastAPI app and checks the lazy page, device and browser selection (including mobile Firefox), every locator strategy, each assertion's pass and failure message, the `RuntimeError` on late configuration, manual screenshots (viewport, full page, test-named and custom-named), failure screenshots, server start-up and shutdown, that `BrowserTestCase.get_application()` selects the served app and `query()` runs on the server loop, and that opening a page with no application raises. The tests skip when a browser is not installed.
- `example/browser-testing/tests/browser/test_registration_page.py` passes on mobile Firefox against the real app, as do tests that sign up a new account and reject a wrong password, and the existing async `HttpTestCase` test still passes after them.
- The full framework suite passes with coverage at or above the threshold.
