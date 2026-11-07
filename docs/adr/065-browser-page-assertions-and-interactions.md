# 065. Browser page assertions, interactions and context options

Date: 2026-11-07

## Problem

ADR 063 gave `Page` a handful of actions and assertions. Tests written against Pest's browser plugin (and Dusk before it) expect a much larger vocabulary: element assertions (`assertSeeIn`, `assertCount`, `assertAttribute`, `assertVisible`…), URL part assertions (`assertHostIs`, `assertQueryStringHas`…), console and JavaScript error checks, keyboard input, frames, file uploads, and per-page timezone, locale and user agent. Without them every test drops down to `page.playwright` and raw Playwright.

## Alternatives

1. **Leave the extras to `page.playwright`.** No work, but the fluent chain breaks for common checks and failures read as Playwright timeouts.
2. **One flat `Page` class with everything.** Simple, but the module grows past a thousand lines and mixes configuration, actions and assertions.
3. **Pest's vocabulary in snake_case, split into a base class (configuration, opening, helpers), an interactions mixin and an assertions mixin, composed into `Page`.**

## Decision

Option 3. `fastapi_startkit.playwright.Page` keeps its import path and composes `BasePage` (`base.py`), `Interactions` (`interactions.py`) and `Assertions` (`assertions.py`). Names follow Pest in snake_case (`assertSeeIn` → `assert_see_in`). As ADR 067 settled, every assertion and chained interaction records a step and returns the page, and the steps run when the page is awaited; readers (`text`, `attribute`, `value`, `script`, `content`) are coroutines that run the pending steps and return the value.

### Finding elements

- Form controls (`fill`, `type`, `type_slowly`, `append`, `clear`, `keys`, `check`, `uncheck`, `select`, `attach`, `value`, `assert_value*`, `assert_checked`/`not_checked`/`indeterminate`, `assert_selected`/`not_selected`, `assert_enabled`/`disabled`) resolve by label, `name`, `id` or placeholder, or by a prefixed selector (ADR 063).
- Buttons and links (`click`, `press`, `press_and_wait_for`, `assert_button_enabled`/`disabled`) resolve by accessible name, `id`, `name` or `type` (ADR 063).
- Element assertions and element readers (`assert_see_in`, `assert_count`, `assert_attribute*`, `assert_visible`, `assert_present`, `hover`, `drag`, `text`, `attribute`, `within_frame`…) take a CSS or XPath selector. `@name` is shorthand for `[data-testid="name"]`, Pest's convention.
- Radios are addressed by group name and value: `radio("plan", "pro")`, `assert_radio_selected("plan", "pro")`.

### Context options

`with_timezone("America/New_York")`, `with_locale("fr-FR")` and `with_user_agent("Googlebot")` are chosen before the page opens, like the device and browser, and are passed to the page's browser context (`timezone_id`, `locale`, `user_agent`). They are applied over the device descriptor, so an explicit user agent wins over the device's. Calling them after the page opened raises `RuntimeError`.

### Assertions

- Title: `assert_title`, `assert_title_contains`.
- Text: `assert_see`, `assert_dont_see`, `assert_see_in(selector, text)`, `assert_dont_see_in`, `assert_see_anything_in(selector)`, `assert_see_nothing_in(selector)`, `assert_see_link(text)`, `assert_dont_see_link(text)` (visible links only). Text comparisons use rendered text (`innerText`) and are case-sensitive.
- Source and script: `assert_source_has(html)`, `assert_source_missing(html)` against `page.content()`; `assert_script(expression, expected=True)` compares the evaluated expression.
- Elements: `assert_count(selector, count)`, `assert_visible`, `assert_present` (in the DOM, visible or not), `assert_not_present` (not in the DOM), `assert_missing` (absent or hidden).
- Attributes: `assert_attribute(selector, name, value)`, `assert_attribute_missing`, `assert_attribute_contains`, `assert_attribute_doesnt_contain`, `assert_aria_attribute(selector, "label", value)` (prefixes `aria-`), `assert_data_attribute(selector, "id", value)` (prefixes `data-`).
- Form state: `assert_checked`, `assert_not_checked`, `assert_indeterminate`, `assert_radio_selected(name, value)`, `assert_radio_not_selected(name, value=None)` (no radio in the group checked when `value` is omitted), `assert_selected(field, value)`, `assert_not_selected` (any selected option of a single or multiple select), `assert_value`, `assert_value_is_not`, `assert_enabled`, `assert_disabled`, `assert_button_enabled`, `assert_button_disabled`.
- URL: `assert_url_is`, `assert_scheme_is`/`_is_not`, `assert_host_is`/`_is_not`, `assert_port_is`/`_is_not` (the URL's port, or the scheme default), `assert_path_is`/`_is_not`, `assert_path_begins_with`, `assert_path_ends_with`, `assert_path_contains`, `assert_query_string_has(name, value=None)`, `assert_query_string_missing(name)`, `assert_fragment_is`/`_is_not`, `assert_fragment_begins_with`. `assert_url_is` and `assert_path_is` keep ADR 063's behaviour of ignoring the query string and fragment.
- Console: each page records console messages and uncaught page errors from the moment it opens. `assert_no_console_logs`, `assert_no_javascript_errors`, and `assert_no_smoke` (both) wait for the `load` event, then fail listing what was recorded.

Every assertion retries until the session timeout, through Playwright's `expect` where it has a matcher and a polling loop (`asyncio.sleep(0.05)` between tries) otherwise. Failures raise `AssertionError` naming the target, the expectation and the current path or URL.

### Interactions

`click`, `press` (a button or link, Dusk's name), `press_and_wait_for(button, seconds=5)` (press, then wait until the button is enabled again), `fill`, `type` (clear, then type key by key), `type_slowly(field, value, delay=100)`, `append` (type at the end without clearing), `clear`, `keys(field, *keys)`, `with_key_down(key, callback)`, `select`, `radio`, `check`, `uncheck`, `attach(field, path)`, `hover`, `drag(source, target)`, `submit()` (submits the focused element's form, or the first form), `within_frame(selector, callback)`, `resize(width, height)`, `wait(seconds)`, `wait_for_text(text)`, `wait_for_key()`, `navigate`, `screenshot`, `debug`, and the readers `text(selector)`, `attribute(selector, name)`, `value(field)`, `script(expression)`, `content()`. `url` stays a property.

- `keys` sends each argument in turn: text is typed, `{Enter}` presses a named key, and a list is a chord: `keys("email", ["{Control}", "a"], "{Backspace}")` presses `Control+a`, then Backspace.
- `with_key_down("Shift", lambda page: page.click("Item"))` holds the key while the callback's steps run and releases it afterwards, also when a step fails. Callbacks may be async functions.
- `within_frame("iframe#editor", lambda frame: frame.fill("body", "hi"))` runs the callback with element lookups scoped to that frame and restores the page scope afterwards. URL and console assertions still read the top page.
- `wait_for_key()` blocks until a key is pressed in the browser window, for use with `--headed`.

### Not in this ADR

`assertNoAccessibilityIssues` needs axe-core in the page, and `assertScreenshotMatches` needs a baseline store and an image diff. Both need a dependency or vendoring decision and are left out until one is made.

## Validation

`fastapi_startkit/tests/playwright/test_page_api.py` serves fixture pages and checks every assertion passing and failing with its message, every interaction's effect in the DOM, the readers' return values, frames, key chords and held keys, file attachment, console and error capture, and timezone, locale and user agent as seen by the page's JavaScript (`Intl.DateTimeFormat().resolvedOptions()`, `navigator.language`, `navigator.userAgent`). The existing browser tests and the example app's tests keep passing.
