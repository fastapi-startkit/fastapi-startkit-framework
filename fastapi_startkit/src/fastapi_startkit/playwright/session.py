import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from typing_extensions import Self

from fastapi_startkit.playwright.server import LiveServer

if TYPE_CHECKING:
    from playwright.async_api import Browser, Playwright
    from playwright.async_api import Page as PlaywrightPage

    from fastapi_startkit.playwright.base import BasePage

BROWSERS = ("chromium", "firefox", "webkit")
CALL_REPORT = pytest.StashKey[pytest.TestReport]()


def ensure_browser(name: str) -> str:
    if name not in BROWSERS:
        raise ValueError(f'Unknown browser "{name}". Choose one of: {", ".join(BROWSERS)}.')
    return name


def slugify(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-") or "page"


class BrowserSession:
    def __init__(self) -> None:
        self.app: Any = None
        self.browser = "chromium"
        self.headed = False
        self.debug = False
        self.timeout = 5000
        self.screenshot_dir = Path("tests/browser/screenshots")
        self.pages: list["BasePage"] = []
        self.test_name: str | None = None
        self._server: LiveServer | None = None
        self._playwright: "Playwright | None" = None
        self._browsers: dict[tuple[str, bool], "Browser"] = {}

    def configure(
        self,
        app: Any = None,
        browser: str | None = None,
        headed: bool | None = None,
        debug: bool | None = None,
        timeout: int | None = None,
        screenshot_dir: str | Path | None = None,
    ) -> Self:
        if app is not None:
            self.app = app
        if browser is not None:
            self.browser = ensure_browser(browser)
        if headed is not None:
            self.headed = headed
        if debug is not None:
            self.debug = debug
        if timeout is not None:
            self.timeout = timeout
        if screenshot_dir is not None:
            self.screenshot_dir = Path(screenshot_dir)
        return self

    @property
    def headless(self) -> bool:
        return not (self.headed or self.debug)

    @property
    def server(self) -> LiveServer:
        if self._server is None or not self._server.running:
            raise RuntimeError("The application server is not running.")
        return self._server

    async def serve(self) -> LiveServer:
        if self.app is None:
            raise RuntimeError(
                "No application to serve. Extend fastapi_startkit.playwright.BrowserTestCase "
                "and return the application from get_application()."
            )
        if self._server is not None and (self._server.app is not self.app or not self._server.running):
            await self.stop_server()
        if self._server is None:
            self._server = await LiveServer(self.app).start()
        return self._server

    async def driver(self) -> "Playwright":
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
        return self._playwright

    async def launch(self, name: str) -> "Browser":
        key = (ensure_browser(name), self.headless)
        if key not in self._browsers:
            browser_type = getattr(await self.driver(), name)
            self._browsers[key] = await browser_type.launch(headless=self.headless)
        return self._browsers[key]

    async def device(self, name: str, browser: str) -> dict[str, Any]:
        try:
            descriptor = dict((await self.driver()).devices[name])
        except KeyError:
            raise ValueError(f'Unknown device "{name}".') from None

        descriptor.pop("default_browser_type", None)
        if browser == "firefox":
            descriptor.pop("is_mobile", None)
        return descriptor

    def track(self, page: "BasePage") -> None:
        self.pages.append(page)

    async def open(
        self, browser: str, device: str | None, context_options: dict[str, Any] | None = None
    ) -> "PlaywrightPage":
        server = await self.serve()
        options = {**(await self.device(device, browser) if device else {}), **(context_options or {})}
        context = await (await self.launch(browser)).new_context(base_url=server.url, **options)
        context.set_default_timeout(self.timeout)
        return await context.new_page()

    def unawaited_pages(self) -> list["BasePage"]:
        return [page for page in self.pages if page.pending]

    async def screenshot_pages(self, name: str) -> list[Path]:
        paths = []
        for index, page in enumerate(page for page in self.pages if page.opened):
            suffix = "" if index == 0 else f"-{index + 1}"
            path = self.screenshot_dir / f"{slugify(name)}{suffix}.png"
            try:
                await page.playwright.screenshot(path=str(path), full_page=True)
            except Exception:
                continue
            paths.append(path)
        return paths

    async def pause_pages(self) -> None:
        for page in self.pages:
            if page.opened:
                await page.playwright.pause()

    async def close_pages(self) -> None:
        for page in self.pages:
            await page.close()
        self.pages.clear()

    async def close_browsers(self) -> None:
        await self.close_pages()
        for browser in self._browsers.values():
            await browser.close()
        self._browsers.clear()

    @property
    def driver_running(self) -> bool:
        return self._playwright is not None

    async def stop_driver(self) -> None:
        await self.close_browsers()
        if self._playwright is not None:
            await self._playwright.stop()
        self._playwright = None

    async def stop_server(self) -> None:
        if self._server is not None:
            await self._server.stop()
            self._server = None

    async def shutdown(self) -> None:
        await self.stop_driver()
        await self.stop_server()


browser_session = BrowserSession()
