import pytest_asyncio

from fastapi_startkit.playwright.session import browser_session


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def browser_session_lifetime():
    yield browser_session
    await browser_session.shutdown()
