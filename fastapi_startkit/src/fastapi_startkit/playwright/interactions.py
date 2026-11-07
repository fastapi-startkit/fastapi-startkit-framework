from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar

from typing_extensions import Self

from fastapi_startkit.playwright import locators
from fastapi_startkit.playwright.base import BasePage
from fastapi_startkit.playwright.session import slugify

if TYPE_CHECKING:
    from playwright.async_api import Locator

T = TypeVar("T")

SUBMIT_FORM = """() => {
    const form = document.activeElement?.form ?? document.querySelector("form");
    if (!form) return false;
    form.requestSubmit();
    return true;
}"""
MOVE_CARET_TO_END = """element => {
    try { element.setSelectionRange(element.value.length, element.value.length); } catch {}
}"""
WAIT_FOR_KEY = """() => new Promise(resolve => {
    document.addEventListener("keydown", event => resolve(event.key), { once: true });
})"""


def key_name(key: str) -> str:
    return key[1:-1] if is_named_key(key) else key


def is_named_key(key: str) -> bool:
    return len(key) > 2 and key.startswith("{") and key.endswith("}")


class Interactions(BasePage):
    def navigate(self, url: str) -> Self:
        async def goto() -> None:
            await self.playwright.goto(url)

        return self._step(goto)

    def click(self, target: str) -> Self:
        return self._act(self._clickable(target), f'click "{target}"', lambda found: found.click())

    def press(self, target: str) -> Self:
        return self._act(self._clickable(target), f'press "{target}"', lambda found: found.click())

    def press_and_wait_for(self, target: str, seconds: float = 5) -> Self:
        async def press_and_wait(found: "Locator") -> None:
            from playwright.async_api import expect

            await found.click()
            await expect(found).to_be_enabled(timeout=seconds * 1000)

        return self._act(self._clickable(target), f'press "{target}" and wait for it', press_and_wait)

    def fill(self, target: str, value: str) -> Self:
        return self._act(self._field(target), f'fill "{target}"', lambda found: found.fill(value))

    def type(self, target: str, value: str) -> Self:
        async def clear_and_type(found: "Locator") -> None:
            await found.clear()
            await found.press_sequentially(value)

        return self._act(self._field(target), f'type into "{target}"', clear_and_type)

    def type_slowly(self, target: str, value: str, delay: float = 100) -> Self:
        async def clear_and_type(found: "Locator") -> None:
            await found.clear()
            await found.press_sequentially(value, delay=delay)

        return self._act(self._field(target), f'type into "{target}"', clear_and_type)

    def append(self, target: str, value: str) -> Self:
        async def type_at_end(found: "Locator") -> None:
            await found.focus()
            await found.evaluate(MOVE_CARET_TO_END)
            await found.press_sequentially(value)

        return self._act(self._field(target), f'append to "{target}"', type_at_end)

    def clear(self, target: str) -> Self:
        return self._act(self._field(target), f'clear "{target}"', lambda found: found.clear())

    def keys(self, target: str, *keys: str | list[str]) -> Self:
        async def send(found: "Locator") -> None:
            await found.focus()
            for key in keys:
                if isinstance(key, list):
                    await found.press("+".join(key_name(part) for part in key))
                elif is_named_key(key):
                    await found.press(key_name(key))
                else:
                    await found.press_sequentially(key)

        return self._act(self._field(target), f'send keys to "{target}"', send)

    def with_key_down(self, key: str, callback: Callable[[Self], Any]) -> Self:
        async def hold() -> None:
            keyboard = self.playwright.keyboard
            await keyboard.down(key_name(key))
            try:
                await self._run_scoped(callback)
            finally:
                await keyboard.up(key_name(key))

        return self._step(hold)

    def check(self, target: str) -> Self:
        return self._act(self._field(target), f'check "{target}"', lambda found: found.check())

    def uncheck(self, target: str) -> Self:
        return self._act(self._field(target), f'uncheck "{target}"', lambda found: found.uncheck())

    def select(self, target: str, option: str | list[str]) -> Self:
        return self._act(
            self._field(target), f'select "{option}" in "{target}"', lambda found: found.select_option(option)
        )

    def radio(self, name: str, value: str) -> Self:
        return self._act(
            lambda: locators.radio(self._root, name, value),
            f'choose "{value}" for "{name}"',
            lambda found: found.check(),
        )

    def attach(self, target: str, path: str | list[str]) -> Self:
        return self._act(self._field(target), f'attach a file to "{target}"', lambda found: found.set_input_files(path))

    def hover(self, target: str) -> Self:
        return self._act(self._element(target), f'hover over "{target}"', lambda found: found.hover())

    def drag(self, source: str, target: str) -> Self:
        return self._act(
            self._element(source),
            f'drag "{source}" to "{target}"',
            lambda found: found.drag_to(self._element(target)().first),
        )

    def submit(self) -> Self:
        async def submit_form() -> None:
            if not await self.playwright.evaluate(SUBMIT_FORM):
                raise AssertionError(f"Unable to submit a form on {self.path}: there is no form.")

        return self._step(submit_form)

    def within_frame(self, selector: str, callback: Callable[[Self], Any]) -> Self:
        async def scoped() -> None:
            previous = self._frame
            self._frame = self._element(selector)().first.content_frame
            try:
                await self._run_scoped(callback)
            finally:
                self._frame = previous

        return self._step(scoped)

    def resize(self, width: int, height: int) -> Self:
        async def set_size() -> None:
            await self.playwright.set_viewport_size({"width": width, "height": height})

        return self._step(set_size)

    def wait(self, seconds: float) -> Self:
        async def pause() -> None:
            await self.playwright.wait_for_timeout(seconds * 1000)

        return self._step(pause)

    def wait_for_text(self, text: str) -> Self:
        return self._expect(
            lambda expect: expect(self._root.locator("body")).to_contain_text(
                text, use_inner_text=True, timeout=self._session.timeout
            ),
            lambda: f'Waited for "{text}" on {self.path}, but it did not appear.',
        )

    def wait_for_key(self) -> Self:
        async def wait_for_keydown() -> None:
            await self.playwright.evaluate(WAIT_FOR_KEY)

        return self._step(wait_for_keydown)

    def screenshot(self, full_page: bool = False, filename: str | None = None) -> Self:
        async def capture() -> None:
            name = slugify(filename or self._session.test_name or self.path)
            path = self._session.screenshot_dir / (name if name.endswith(".png") else f"{name}.png")
            await self.playwright.screenshot(path=str(path), full_page=full_page)

        return self._step(capture)

    def debug(self) -> Self:
        async def pause() -> None:
            await self.playwright.pause()

        return self._step(pause)

    async def text(self, selector: str) -> str:
        return await self._read(
            self._element(selector), f'read the text of "{selector}"', lambda found: found.inner_text()
        )

    async def attribute(self, selector: str, name: str) -> str | None:
        return await self._read(
            self._element(selector), f'read "{name}" of "{selector}"', lambda found: found.get_attribute(name)
        )

    async def value(self, target: str) -> str:
        return await self._read(self._field(target), f'read the value of "{target}"', lambda found: found.input_value())

    async def script(self, expression: str, argument: Any = None) -> Any:
        await self
        return await self.playwright.evaluate(expression, argument)

    async def content(self) -> str:
        await self
        return await self.playwright.content()

    def _clickable(self, target: str) -> Callable[[], "Locator"]:
        return lambda: locators.clickable(self._root, target)

    def _field(self, target: str) -> Callable[[], "Locator"]:
        return lambda: locators.field(self._root, target)

    def _element(self, target: str) -> Callable[[], "Locator"]:
        return lambda: locators.element(self._root, target)

    async def _read(
        self, locate: Callable[[], "Locator"], description: str, read: Callable[["Locator"], Awaitable[T]]
    ) -> T:
        from playwright.async_api import Error

        await self
        try:
            return await read(locate().first)
        except Error as error:
            raise AssertionError(f"Unable to {description} on {self.path}.") from error
