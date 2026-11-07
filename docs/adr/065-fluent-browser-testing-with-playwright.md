# 065. Fluent async browser testing with Playwright

Date: 2026-11-07

## Problem

Apps built on the framework, especially Inertia apps, can't test what a user sees in a real browser. `HttpTestCase` sends requests through `ASGITransport`, so it never runs the frontend, follows a client-side Inertia visit, or fills in a form.

Raw Playwright against a live server means a lot of hand work:

- starting uvicorn yourself;
- managing browsers, contexts and base URLs;
- writing a CSS selector for every button.

There is also no way to reset a database that the server writes to from its own connections. The framework is async by default, so browser tests should be too. They should `await` the ORM and factories on the same connection the application uses, and read like a user's script, as Pest's browser plugin does:

```python
class RegistrationTest(TestCase, DatabaseTruncation):
    async def test_user_can_sign_in(self) -> None:
        await UserFactory.new().create({"email": "ada@example.com"})

        await (
            visit("/login")
            .on().mobile().firefox()
            .fill("email", "ada@example.com")
            .fill("password", "password")
            .click("submit")
            .assert_path_is("/dashboard")
        )
```

## Alternatives

1. **`pytest-playwright`.** It provides `page` fixtures, but no live server, no fluent chain and no lookup by visible text. Its options and fixtures would shape our API.
2. **Sync Playwright, with uvicorn on a thread and its own loop.** The chain reads well. But the ORM's connections belong to the server loop, so every database touch needs a wrapper that ships the coroutine across threads. The sync driver also blocks any loop that calls it.
3. **Async tests on their own loop, with sync Playwright on a worker thread.** The test and the app would use different connections, which needs loop-keyed connection caches. Every raw Playwright call would need marshalling.
4. **Everything on one loop.** The test, the app server, Playwright's async API and the database all share one loop. The page chain records steps and runs them when awaited. The database is reset by truncation.

For the database, `RefreshDatabase`'s rollback can't cover writes the live server makes on its own connections. Migrating before every test is correct but slow. Laravel truncates instead.

## Decision

Option 4, shipped as `fastapi_startkit.playwright` behind the `playwright` extra. The extra adds `playwright` and `pytest-asyncio` on top of `fastapi`. Truncation lives in `fastapi_startkit.masoniteorm.testing.DatabaseTruncation`.

### Page chains

`visit(path)` returns a `Page` without opening anything. It is composed of three parts:

- `BasePage` (`base.py`): configuration, opening and step running.
- `Interactions` (`interactions.py`).
- `Assertions` (`assertions.py`).

Configuration is synchronous and must happen before the page opens; doing it later raises `RuntimeError`. It covers:

- devices: `.on().mobile()`, `.tablet()`, `.desktop()`, `.device("Pixel 7")`;
- browsers: `.chromium()`, `.firefox()`, `.webkit()`;
- context options: `with_timezone`, `with_locale`, `with_user_agent`. These are applied over the device descriptor, so an explicit user agent wins.

Firefox doesn't support `is_mobile`. For Firefox the flag is dropped, and the viewport, user agent and touch support are kept.

How steps run:

- Actions and assertions record a step and return the page. Awaiting the page opens it if needed, runs the steps in order and returns the page.
- A failing step drops the steps after it and raises `AssertionError`.
- The readers `text`, `attribute`, `value`, `script` and `content` are coroutines. Each one runs the pending steps first.
- `page.playwright` is the opened async Playwright page. Using it before the page has been awaited raises `RuntimeError`.
- A chain that is never awaited would silently test nothing. So a test fails with `"... was never awaited"` if a page was never awaited or closed, or still has recorded steps when it ends. A bare `visit("/")` counts.

### Finding elements

Elements are found by what a user sees. The candidates are combined with `Locator.or_()`, so Playwright's auto-waiting still applies.

| What | Resolved by | Used by |
|---|---|---|
| Buttons and links | accessible name, `id`, `name` or `type` (so `click("submit")` presses the submit button) | `click`, `press`, `press_and_wait_for`, `assert_button_enabled`, `assert_button_disabled` |
| Form controls | label, `name`, `id` or placeholder | `fill`, `type`, `check`, `select`, `value`, `assert_value`, and so on |
| Elements | CSS or XPath; `@name` is shorthand for `[data-testid="name"]` | element assertions, `hover`, `drag`, `text`, `within_frame` |
| Radios | group name and value | `radio("plan", "pro")` |

A target that starts with `#`, `.`, `[`, `//`, `css=`, `xpath=` or `text=` is used as a selector. Values are placed in quoted attribute selectors, so any text is a valid target.

### Vocabulary

Names follow Pest's browser plugin, in snake_case.

**Assertions:**

- **Title:** `assert_title`, `assert_title_contains`.
- **Text:** `assert_see`, `assert_dont_see`, `assert_see_in`, `assert_dont_see_in`, `assert_see_anything_in`, `assert_see_nothing_in`, `assert_see_link`, `assert_dont_see_link`. These compare rendered text and are case-sensitive. `assert_dont_see_in` first requires the selector to match, so a typo in it fails instead of passing.
- **Source and script:** `assert_source_has`, `assert_source_missing`, `assert_script`.
- **Elements:** `assert_count`, `assert_visible`, `assert_present`, `assert_not_present`, `assert_missing`.
- **Attributes:** `assert_attribute`, `assert_attribute_missing`, `assert_attribute_contains`, `assert_attribute_doesnt_contain`, `assert_aria_attribute`, `assert_data_attribute`.
- **Form state:** `assert_checked`, `assert_not_checked`, `assert_indeterminate`, `assert_radio_selected`, `assert_radio_not_selected`, `assert_selected`, `assert_not_selected`, `assert_value`, `assert_value_is_not`, `assert_enabled`, `assert_disabled`.
- **URL:**
  - Every part has an assertion and its negation: scheme, host, port (the scheme's default when none is given), path and fragment.
  - The path also has `begins_with`, `ends_with` and `contains`; the fragment has `begins_with`.
  - `assert_query_string_has` and `assert_query_string_missing`.
  - `assert_url_is` and `assert_path_is` ignore the query string and fragment.
- **Console:** `assert_no_console_logs`, `assert_no_javascript_errors`, `assert_no_smoke`. These wait for the `load` event, then list what the page recorded.

Every assertion retries until the timeout. It uses Playwright's `expect` where a matcher exists, and otherwise polls every 50 ms. A failure names the target, the expectation and the current path.

**Interactions:**

- **Clicking:** `click`, `press`, `press_and_wait_for`.
- **Typing:**
  - `fill`, `type`, `type_slowly`, `append`, `clear`.
  - `keys(field, *keys)`: text is typed, `{Enter}` is a named key, and a list is a chord.
  - `with_key_down(key, callback)`.
- **Choosing:** `select`, `radio`, `check`, `uncheck`, `attach`.
- **Pointer:** `hover`, `drag`.
- **Page:** `submit`, `within_frame(selector, callback)`, `resize`, `navigate`.
- **Waiting:** `wait`, `wait_for_text`, `wait_for_key`.
- **Debugging:** `screenshot(full_page=, filename=)`, `debug`.

`within_frame` scopes element lookups to the frame. URL and console assertions still read the top page. The callbacks of `with_key_down` and `within_frame` add steps that run in place, and they may be async. `screenshot` writes into `browser_screenshot_dir`, named after the test unless a filename is given.

### One session loop

- **Test class.** `BrowserTestCase` is marked `pytest.mark.asyncio(loop_scope="session")`. A sync test method fails with a message asking for `async def`.
- **Shared loop.** The live server, the Playwright driver, the browsers and the app's database connections are all created on that loop and live until the session ends.
- **Live server.** `LiveServer.start()` binds a free port on `127.0.0.1` and runs `uvicorn.Server.serve` as a task. Signal capture is disabled, so Ctrl-C still interrupts pytest.
- **Pages.** There is one browser per engine and one context per page, with `base_url` set to the server.
- **Per test**, an autouse fixture:
  1. serves the app returned by `get_application()` (a different app restarts the server);
  2. awaits `asyncStartTestRun()` and `asyncStopTestRun()`;
  3. takes failure screenshots;
  4. pauses failed tests under `--browser-debug`;
  5. checks for unawaited chains;
  6. closes the test's pages.
- **User fixtures.** A user's own async fixtures need `loop_scope="session"`, or the project sets `asyncio_default_fixture_loop_scope = "session"`.

### Plugin

A `pytest11` entry point registers `fastapi_startkit.pytest_plugin`. It loads the browser plugin only when `playwright` and `pytest-asyncio` are installed, so projects without the extra see no options or hooks. The entry point declares the options itself and registers `fastapi_startkit.playwright.plugin` from `pytest_configure`, after pytest-cov starts. Importing the package from the entry point hid every import and `def` line from coverage. The browser plugin imports nothing from Playwright until a page opens.

- **Ini options:** `browser_default` (`chromium`), `browser_timeout` (5000 ms) and `browser_screenshot_dir` (`tests/browser/screenshots`).
- **`--headed`:** shows the browsers. The plugin reuses this option if `pytest-playwright` already defines it.
- **`--browser-debug`:** browsers run headed and each open page of a failed test pauses in the Playwright inspector. pytest's own `--debug` writes a debug log and is left alone.
- **`page.debug()`:** limits the run to the tests that call it. The plugin finds those tests by parsing their source at collection, and only looks at methods of `BrowserTestCase` subclasses, so a `logger.debug()` or `MagicMock().debug()` elsewhere never deselects other tests. They run headed and pause at that point.
- **Shutdown:** a session fixture shuts everything down on the session loop. It is registered only when pytest-asyncio is installed.

### Database truncation

`DatabaseTruncation` hooks into `asyncStartTestRun`, so it works the same in `TestCase` and `BrowserTestCase`.

- The first test of the process runs `migrate:fresh` once per `(connection, migration_directory)` pair.
- Each later test empties every table on a single checked-out connection, committing after each statement, so MySQL's `FOREIGN_KEY_CHECKS` toggle applies to its `TRUNCATE`. Postgres uses one `TRUNCATE ... RESTART IDENTITY CASCADE` over all tables, because it refuses to truncate a referenced table on its own and `DISABLE TRIGGER ALL` needs a superuser. SQLite and SQL Server use the platform's foreign-key-safe truncate. It skips `migrations`, `sqlite_*` and `except_tables`, or empties only `tables_to_truncate` when that is set.
- After the reset it seeds: `DatabaseSeeder` by default, or the class named by `seeder`. `seed = False` skips seeding.
- `connection`, `seed_directory` and `migration_directory` are configurable.

### Deferred

- **Accessibility and screenshot-diff assertions** (`assertNoAccessibilityIssues`, `assertScreenshotMatches`): they need axe-core and an image-diff baseline store, so they wait for a dependency decision.
- **`assert_authenticated`:** it belongs with the auth package.

## Validation

- **`tests/playwright/test_browser.py`:** covers
  - lazy chains, step order and readers flushing pending steps;
  - nested callbacks, dropped steps after a failure, and unawaited-chain failures;
  - devices, browsers and every locator strategy;
  - screenshots and debug pauses;
  - the live server's start, stop and failure messages;
  - `get_application()` switching servers.
- **`tests/playwright/test_page_api.py`:** serves fixture pages and checks:
  - every assertion, both passing and failing with its message;
  - every interaction's effect in the DOM;
  - the readers, frames, key chords, file attachment and console capture;
  - timezone, locale and user agent, as the page's JavaScript reports them.
- **`tests/masoniteorm/testing/test_database_truncation.py`:** covers fresh migration first, truncation that respects the skipped tables, the seeding options, and truncation through a `BrowserTestCase`.
- **Full suite:** passes with coverage above the threshold.
- **CI:** the test workflow runs `playwright install --with-deps chromium` before pytest. The shared `requires_chromium` fixture in `tests/playwright/conftest.py` skips every class that launches a browser when Chromium is missing.
