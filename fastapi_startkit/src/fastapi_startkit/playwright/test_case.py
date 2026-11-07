import inspect
from abc import abstractmethod
from typing import Any

import pytest
import pytest_asyncio

from fastapi_startkit.playwright.session import CALL_REPORT, browser_session


class BrowserTestCase:
    pytestmark = [pytest.mark.asyncio(loop_scope="session"), pytest.mark.usefixtures("browser_session_lifetime")]

    @abstractmethod
    def get_application(self) -> Any: ...

    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def browser_test(self, request: pytest.FixtureRequest):
        if not inspect.iscoroutinefunction(request.function):
            pytest.fail(
                f"{request.node.name} must be declared with async def: browser tests run on the session event loop.",
                pytrace=False,
            )

        browser_session.configure(app=self.get_application())
        browser_session.test_name = request.node.nodeid
        await browser_session.serve()
        await self._call_hook("asyncStartTestRun")
        try:
            yield
            await self._call_hook("asyncStopTestRun")
            report = request.node.stash.get(CALL_REPORT, None)
            if report is not None and report.failed:
                for path in await browser_session.screenshot_pages(request.node.nodeid):
                    report.sections.append(("Browser screenshot", str(path)))
                if browser_session.debug:
                    await browser_session.pause_pages()
            elif unawaited := browser_session.unawaited_pages():
                chains = ", ".join(page.describe() for page in unawaited)
                pytest.fail(f"{chains} was never awaited, so its steps did not run.", pytrace=False)
        finally:
            await browser_session.close_pages()
            browser_session.test_name = None

    async def _call_hook(self, name: str) -> None:
        hook = getattr(self, name, None)
        if hook is not None:
            await hook()
