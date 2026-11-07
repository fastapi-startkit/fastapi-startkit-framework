import asyncio
import inspect
from collections.abc import Awaitable, Callable, Generator
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from typing_extensions import Self

from fastapi_startkit.playwright.session import BrowserSession, ensure_browser

if TYPE_CHECKING:
    from playwright.async_api import FrameLocator, Locator
    from playwright.async_api import Page as PlaywrightPage

    from fastapi_startkit.playwright.locators import Root

Step = Callable[[], Awaitable[Any]]
Message = Callable[[], str | Awaitable[str]]
POLL_INTERVAL = 0.05


class BasePage:
    def __init__(self, session: BrowserSession, url: str):
        self._session = session
        self._url = url
        self._browser: str | None = None
        self._device: str | None = None
        self._context_options: dict[str, Any] = {}
        self._page: "PlaywrightPage | None" = None
        self._frame: "FrameLocator | None" = None
        self._steps: list[Step] = []
        self._settled = False
        self.console_logs: list[str] = []
        self.javascript_errors: list[str] = []
        session.track(self)

    def device(self, name: str | None) -> Self:
        self._ensure_configurable()
        self._device = name
        return self

    def browser(self, name: str) -> Self:
        self._ensure_configurable()
        self._browser = ensure_browser(name)
        return self

    def chromium(self) -> Self:
        return self.browser("chromium")

    def firefox(self) -> Self:
        return self.browser("firefox")

    def webkit(self) -> Self:
        return self.browser("webkit")

    def with_timezone(self, timezone: str) -> Self:
        return self._with_context_option("timezone_id", timezone)

    def with_locale(self, locale: str) -> Self:
        return self._with_context_option("locale", locale)

    def with_user_agent(self, user_agent: str) -> Self:
        return self._with_context_option("user_agent", user_agent)

    def __await__(self) -> Generator[Any, None, Self]:
        return self._run().__await__()

    @property
    def opened(self) -> bool:
        return self._page is not None

    @property
    def pending(self) -> bool:
        return not self._settled or bool(self._steps)

    @property
    def playwright(self) -> "PlaywrightPage":
        if self._page is None:
            raise RuntimeError(f'Await visit("{self._url}") before using page.playwright.')
        return self._page

    @property
    def url(self) -> str:
        return self.playwright.url

    @property
    def path(self) -> str:
        parts = urlsplit(self.url)
        return parts.path + (f"?{parts.query}" if parts.query else "")

    async def close(self) -> None:
        self._settled = True
        self._steps.clear()
        if self._page is not None:
            await self._page.context.close()
            self._page = None
            self._frame = None

    def describe(self) -> str:
        return f'visit("{self._url}")'

    @property
    def _root(self) -> "Root":
        return self._frame if self._frame is not None else self.playwright

    async def _run(self) -> Self:
        self._settled = True
        await self._open()
        try:
            while self._steps:
                await self._steps.pop(0)()
        finally:
            self._steps.clear()
        return self

    async def _open(self) -> None:
        if self._page is not None:
            return
        page = await self._session.open(self._browser or self._session.browser, self._device, self._context_options)
        page.on("console", lambda message: self.console_logs.append(message.text))
        page.on("pageerror", lambda error: self.javascript_errors.append(str(error)))
        self._page = page
        await page.goto(self._url)

    async def _run_scoped(self, callback: Callable[[Self], Any]) -> None:
        outer, self._steps = self._steps, []
        try:
            result = callback(self)
            if inspect.isawaitable(result) and result is not self:
                await result
            await self._run()
        finally:
            self._steps = outer

    def _step(self, step: Step) -> Self:
        self._steps.append(step)
        return self

    def _with_context_option(self, name: str, value: Any) -> Self:
        self._ensure_configurable()
        self._context_options[name] = value
        return self

    def _ensure_configurable(self) -> None:
        if self._page is not None:
            raise RuntimeError("Choose the device and browser before interacting with the page.")

    def _act(
        self, locate: Callable[[], "Locator"], description: str, action: Callable[["Locator"], Awaitable[Any]]
    ) -> Self:
        async def act() -> None:
            from playwright.async_api import Error

            try:
                await action(locate().first)
            except Error as error:
                raise AssertionError(f"Unable to {description} on {self.path}.") from error

        return self._step(act)

    def _expect(self, check: Callable[[Any], Awaitable[Any]], message: Message) -> Self:
        async def expectation() -> None:
            from playwright.async_api import expect

            try:
                await check(expect)
            except AssertionError as error:
                raise AssertionError(await resolve(message)) from error

        return self._step(expectation)

    def _wait_until(self, condition: Callable[[], bool | Awaitable[bool]], message: Message) -> Self:
        async def poll() -> None:
            from playwright.async_api import Error

            loop = asyncio.get_running_loop()
            deadline = loop.time() + self._session.timeout / 1000
            while True:
                try:
                    if await resolve(condition):
                        return
                except Error:
                    pass
                if loop.time() >= deadline:
                    raise AssertionError(await resolve(message))
                await asyncio.sleep(POLL_INTERVAL)

        return self._step(poll)


async def resolve(produce: Callable[[], Any]) -> Any:
    result = produce()
    return await result if inspect.isawaitable(result) else result
