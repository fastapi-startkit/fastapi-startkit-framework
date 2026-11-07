import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import SplitResult, parse_qs, urlsplit

from typing_extensions import Self

from fastapi_startkit.playwright import locators
from fastapi_startkit.playwright.base import BasePage, Message

if TYPE_CHECKING:
    from playwright.async_api import Locator

IGNORED_URL_SUFFIX = r"(?:[?#].*)?$"
DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}
ANYTHING = re.compile(r"\S")
NOTHING = re.compile(r"^\s*$")
SELECTED_VALUES = (
    "elements => elements.length ? Array.from(elements[0].selectedOptions ?? [], option => option.value) : null"
)


def port_of(parts: SplitResult) -> int | None:
    return parts.port or DEFAULT_PORTS.get(parts.scheme)


def query_of(parts: SplitResult) -> dict[str, list[str]]:
    return parse_qs(parts.query, keep_blank_values=True)


def containing(value: str) -> re.Pattern[str]:
    return re.compile(re.escape(value))


class Assertions(BasePage):
    def assert_title(self, title: str) -> Self:
        return self._expect(
            lambda expect: expect(self.playwright).to_have_title(title, timeout=self._session.timeout),
            self._title_message(f'to be "{title}"'),
        )

    def assert_title_contains(self, text: str) -> Self:
        return self._expect(
            lambda expect: expect(self.playwright).to_have_title(containing(text), timeout=self._session.timeout),
            self._title_message(f'to contain "{text}"'),
        )

    def assert_see(self, text: str) -> Self:
        return self._see_in("body", text, lambda: f'Expected to see "{text}" on {self.path}.')

    def assert_dont_see(self, text: str) -> Self:
        return self._dont_see_in("body", text, lambda: f'Expected not to see "{text}" on {self.path}.')

    def assert_see_in(self, selector: str, text: str) -> Self:
        return self._see_in(selector, text, lambda: f'Expected to see "{text}" in "{selector}" on {self.path}.')

    def assert_dont_see_in(self, selector: str, text: str) -> Self:
        return self._dont_see_in(
            selector, text, lambda: f'Expected not to see "{text}" in "{selector}" on {self.path}.'
        )

    def assert_see_anything_in(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_have_text(
                ANYTHING, use_inner_text=True, timeout=self._session.timeout
            ),
            lambda: f'Expected to see text in "{selector}" on {self.path}.',
        )

    def assert_see_nothing_in(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_have_text(
                NOTHING, use_inner_text=True, timeout=self._session.timeout
            ),
            lambda: f'Expected "{selector}" to be empty on {self.path}.',
        )

    def assert_see_link(self, text: str) -> Self:
        return self._expect(
            lambda expect: expect(self._link(text).first).to_be_visible(timeout=self._session.timeout),
            lambda: f'Expected to see the link "{text}" on {self.path}.',
        )

    def assert_dont_see_link(self, text: str) -> Self:
        return self._expect(
            lambda expect: expect(self._link(text)).to_have_count(0, timeout=self._session.timeout),
            lambda: f'Expected not to see the link "{text}" on {self.path}.',
        )

    def assert_source_has(self, html: str) -> Self:
        async def has() -> bool:
            return html in await self.playwright.content()

        return self._wait_until(has, lambda: f'Expected the source of {self.path} to contain "{html}".')

    def assert_source_missing(self, html: str) -> Self:
        async def missing() -> bool:
            return html not in await self.playwright.content()

        return self._wait_until(missing, lambda: f'Expected the source of {self.path} not to contain "{html}".')

    def assert_script(self, expression: str, expected: Any = True) -> Self:
        returned: list[Any] = [None]

        async def returns() -> bool:
            returned[0] = await self.playwright.evaluate(expression)
            return returned[0] == expected

        return self._wait_until(
            returns,
            lambda: (
                f"Expected the script `{expression}` to return {expected!r} on {self.path}, "
                f"but it returned {returned[0]!r}."
            ),
        )

    def assert_count(self, selector: str, count: int) -> Self:
        async def message() -> str:
            found = await self._find(selector).count()
            return f'Expected {count} elements matching "{selector}" on {self.path}, but found {found}.'

        return self._expect(
            lambda expect: expect(self._find(selector)).to_have_count(count, timeout=self._session.timeout),
            message,
        )

    def assert_visible(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_be_visible(timeout=self._session.timeout),
            lambda: f'Expected "{selector}" to be visible on {self.path}.',
        )

    def assert_present(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_be_attached(timeout=self._session.timeout),
            lambda: f'Expected "{selector}" to be present on {self.path}.',
        )

    def assert_not_present(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector)).to_have_count(0, timeout=self._session.timeout),
            lambda: f'Expected "{selector}" not to be present on {self.path}.',
        )

    def assert_missing(self, selector: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_be_hidden(timeout=self._session.timeout),
            lambda: f'Expected "{selector}" to be missing or hidden on {self.path}.',
        )

    def assert_attribute(self, selector: str, name: str, value: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_have_attribute(
                name, value, timeout=self._session.timeout
            ),
            lambda: f'Expected "{selector}" to have {name}="{value}" on {self.path}.',
        )

    def assert_attribute_missing(self, selector: str, name: str) -> Self:
        async def check(expect: Any) -> None:
            found = self._find(selector).first
            await expect(found).to_be_attached(timeout=self._session.timeout)
            await expect(found).not_to_have_attribute(name, timeout=self._session.timeout)

        return self._expect(check, lambda: f'Expected "{selector}" not to have the attribute "{name}" on {self.path}.')

    def assert_attribute_contains(self, selector: str, name: str, value: str) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_have_attribute(
                name, containing(value), timeout=self._session.timeout
            ),
            lambda: f'Expected the "{name}" of "{selector}" to contain "{value}" on {self.path}.',
        )

    def assert_attribute_doesnt_contain(self, selector: str, name: str, value: str) -> Self:
        async def check(expect: Any) -> None:
            found = self._find(selector).first
            await expect(found).to_have_attribute(name, timeout=self._session.timeout)
            await expect(found).not_to_have_attribute(name, containing(value), timeout=self._session.timeout)

        return self._expect(
            check, lambda: f'Expected the "{name}" of "{selector}" not to contain "{value}" on {self.path}.'
        )

    def assert_aria_attribute(self, selector: str, name: str, value: str) -> Self:
        return self.assert_attribute(selector, f"aria-{name}", value)

    def assert_data_attribute(self, selector: str, name: str, value: str) -> Self:
        return self.assert_attribute(selector, f"data-{name}", value)

    def assert_checked(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_be_checked(timeout=self._session.timeout),
            lambda: f'Expected "{target}" to be checked on {self.path}.',
        )

    def assert_not_checked(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_be_checked(checked=False, timeout=self._session.timeout),
            lambda: f'Expected "{target}" not to be checked on {self.path}.',
        )

    def assert_indeterminate(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_be_checked(
                indeterminate=True, timeout=self._session.timeout
            ),
            lambda: f'Expected "{target}" to be indeterminate on {self.path}.',
        )

    def assert_radio_selected(self, name: str, value: str) -> Self:
        return self._expect(
            lambda expect: expect(locators.radio(self._root, name, value).first).to_be_checked(
                timeout=self._session.timeout
            ),
            lambda: f'Expected the radio "{name}" to have "{value}" selected on {self.path}.',
        )

    def assert_radio_not_selected(self, name: str, value: str | None = None) -> Self:
        def checked() -> "Locator":
            return locators.radio(self._root, name, value).and_(self._root.locator(":checked"))

        expectation = f'"{value}" selected' if value is not None else "a selection"
        return self._expect(
            lambda expect: expect(checked()).to_have_count(0, timeout=self._session.timeout),
            lambda: f'Expected the radio "{name}" not to have {expectation} on {self.path}.',
        )

    def assert_selected(self, target: str, value: str) -> Self:
        async def selected() -> bool:
            return value in (await self._selected_values(target) or [])

        return self._wait_until(selected, lambda: f'Expected "{value}" to be selected in "{target}" on {self.path}.')

    def assert_not_selected(self, target: str, value: str) -> Self:
        async def not_selected() -> bool:
            values = await self._selected_values(target)
            return values is not None and value not in values

        return self._wait_until(
            not_selected, lambda: f'Expected "{value}" not to be selected in "{target}" on {self.path}.'
        )

    def assert_value(self, target: str, value: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_have_value(value, timeout=self._session.timeout),
            lambda: f'Expected "{target}" to have the value "{value}" on {self.path}.',
        )

    def assert_value_is_not(self, target: str, value: str) -> Self:
        async def check(expect: Any) -> None:
            await expect(self._control(target)).to_be_attached(timeout=self._session.timeout)
            await expect(self._control(target)).not_to_have_value(value, timeout=self._session.timeout)

        return self._expect(check, lambda: f'Expected "{target}" not to have the value "{value}" on {self.path}.')

    def assert_enabled(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_be_enabled(timeout=self._session.timeout),
            lambda: f'Expected "{target}" to be enabled on {self.path}.',
        )

    def assert_disabled(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._control(target)).to_be_disabled(timeout=self._session.timeout),
            lambda: f'Expected "{target}" to be disabled on {self.path}.',
        )

    def assert_button_enabled(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._button(target)).to_be_enabled(timeout=self._session.timeout),
            lambda: f'Expected the button "{target}" to be enabled on {self.path}.',
        )

    def assert_button_disabled(self, target: str) -> Self:
        return self._expect(
            lambda expect: expect(self._button(target)).to_be_disabled(timeout=self._session.timeout),
            lambda: f'Expected the button "{target}" to be disabled on {self.path}.',
        )

    def assert_url_is(self, url: str) -> Self:
        def expected() -> str:
            return url if "://" in url else self._session.server.url + url

        return self._expect(
            lambda expect: expect(self.playwright).to_have_url(
                re.compile("^" + re.escape(expected()) + IGNORED_URL_SUFFIX), timeout=self._session.timeout
            ),
            lambda: f'Expected the URL to be "{expected()}", but it was "{self.url}".',
        )

    def assert_scheme_is(self, scheme: str) -> Self:
        return self._url_part("scheme", lambda parts: parts.scheme == scheme, f'to be "{scheme}"')

    def assert_scheme_is_not(self, scheme: str) -> Self:
        return self._url_part("scheme", lambda parts: parts.scheme != scheme, f'not to be "{scheme}"')

    def assert_host_is(self, host: str) -> Self:
        return self._url_part("host", lambda parts: parts.hostname == host, f'to be "{host}"')

    def assert_host_is_not(self, host: str) -> Self:
        return self._url_part("host", lambda parts: parts.hostname != host, f'not to be "{host}"')

    def assert_port_is(self, port: int | str) -> Self:
        return self._url_part("port", lambda parts: str(port_of(parts)) == str(port), f'to be "{port}"')

    def assert_port_is_not(self, port: int | str) -> Self:
        return self._url_part("port", lambda parts: str(port_of(parts)) != str(port), f'not to be "{port}"')

    def assert_path_is(self, path: str) -> Self:
        pattern = re.compile(r"^[a-z]+://[^/]+" + re.escape(path) + IGNORED_URL_SUFFIX)
        return self._expect(
            lambda expect: expect(self.playwright).to_have_url(pattern, timeout=self._session.timeout),
            lambda: f'Expected the path to be "{path}", but it was "{self.path}".',
        )

    def assert_path_is_not(self, path: str) -> Self:
        return self._url_part("path", lambda parts: parts.path != path, f'not to be "{path}"')

    def assert_path_begins_with(self, prefix: str) -> Self:
        return self._url_part("path", lambda parts: parts.path.startswith(prefix), f'to begin with "{prefix}"')

    def assert_path_ends_with(self, suffix: str) -> Self:
        return self._url_part("path", lambda parts: parts.path.endswith(suffix), f'to end with "{suffix}"')

    def assert_path_contains(self, text: str) -> Self:
        return self._url_part("path", lambda parts: text in parts.path, f'to contain "{text}"')

    def assert_query_string_has(self, name: str, value: str | None = None) -> Self:
        def has(parts: SplitResult) -> bool:
            query = query_of(parts)
            return name in query and (value is None or value in query[name])

        expectation = f'to have "{name}"' + (f' set to "{value}"' if value is not None else "")
        return self._url_part("query string", has, expectation)

    def assert_query_string_missing(self, name: str) -> Self:
        return self._url_part("query string", lambda parts: name not in query_of(parts), f'not to have "{name}"')

    def assert_fragment_is(self, fragment: str) -> Self:
        return self._url_part("fragment", lambda parts: parts.fragment == fragment, f'to be "{fragment}"')

    def assert_fragment_is_not(self, fragment: str) -> Self:
        return self._url_part("fragment", lambda parts: parts.fragment != fragment, f'not to be "{fragment}"')

    def assert_fragment_begins_with(self, prefix: str) -> Self:
        return self._url_part("fragment", lambda parts: parts.fragment.startswith(prefix), f'to begin with "{prefix}"')

    def assert_no_console_logs(self) -> Self:
        return self._nothing_recorded("console logs", lambda: self.console_logs)

    def assert_no_javascript_errors(self) -> Self:
        return self._nothing_recorded("JavaScript errors", lambda: self.javascript_errors)

    def assert_no_smoke(self) -> Self:
        return self.assert_no_console_logs().assert_no_javascript_errors()

    def _find(self, selector: str) -> "Locator":
        return locators.element(self._root, selector)

    def _control(self, target: str) -> "Locator":
        return locators.field(self._root, target).first

    def _button(self, target: str) -> "Locator":
        return locators.clickable(self._root, target).first

    def _link(self, text: str) -> "Locator":
        return self._root.locator("a", has_text=containing(text)).filter(visible=True)

    async def _selected_values(self, target: str) -> list[str] | None:
        return await locators.field(self._root, target).evaluate_all(SELECTED_VALUES)

    def _see_in(self, selector: str, text: str, message: Message) -> Self:
        return self._expect(
            lambda expect: expect(self._find(selector).first).to_contain_text(
                text, use_inner_text=True, timeout=self._session.timeout
            ),
            message,
        )

    def _dont_see_in(self, selector: str, text: str, message: Message) -> Self:
        self._expect(
            lambda expect: expect(self._find(selector).first).to_be_attached(timeout=self._session.timeout),
            lambda: f'Expected to find "{selector}" on {self.path}.',
        )
        return self._expect(
            lambda expect: expect(self._find(selector).first).not_to_contain_text(
                text, use_inner_text=True, timeout=self._session.timeout
            ),
            message,
        )

    def _title_message(self, expectation: str) -> Message:
        async def message() -> str:
            return f'Expected the title {expectation}, but it was "{await self.playwright.title()}".'

        return message

    def _url_part(self, label: str, matches: Callable[[SplitResult], bool], expectation: str) -> Self:
        return self._wait_until(
            lambda: matches(urlsplit(self.url)),
            lambda: f'Expected the {label} {expectation}, but the URL was "{self.url}".',
        )

    def _nothing_recorded(self, label: str, recorded: Callable[[], list[str]]) -> Self:
        async def check() -> None:
            await self.playwright.wait_for_load_state("load")
            if recorded():
                listed = "\n".join(f"  - {entry}" for entry in recorded())
                raise AssertionError(f"Expected no {label} on {self.path}, but found:\n{listed}")

        return self._step(check)
